"""Adapter for JIRA Cloud (and best-effort JIRA Server) via REST API v3.

Env:
    SPEC_SOURCE=jira
    JIRA_BASE_URL=https://yourorg.atlassian.net   (no trailing slash)
    JIRA_EMAIL=you@example.com                     Cloud uses Basic auth
                                                    with email + API token
    JIRA_API_TOKEN=...                             From id.atlassian.com →
                                                    Security → API tokens
    SPEC_PROJECT_KEY=PROJ                          Project key (optional;
                                                    omit to list across all
                                                    projects the API user
                                                    has access to)

Auth: Basic <base64(email:token)>. JIRA Server installations that allow
plain bearer tokens also work — set JIRA_EMAIL to anything non-empty and
the server-side auth will ignore it.

Description body: JIRA Cloud returns descriptions as ADF (Atlassian
Document Format) JSON. We flatten ADF → markdown so the existing
parse_spec heading / list-item detection works. Common nodes (paragraph,
heading, bulletList, orderedList, listItem, text) are translated;
unknown node types fall through with inner text preserved.

Zero new deps — stdlib urllib + base64.
"""

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

from .. import config
from . import register
from .base import Spec, SpecSource, SpecSummary


class JiraUnavailable(RuntimeError):
    """Raised when the JIRA API call fails or env vars are missing.
    Message is shown to the AI client; keep it actionable."""


_TIMEOUT_S = 20
_API_PATH = "/rest/api/3"


# ---------- HTTP --------------------------------------------------------


def _check_auth() -> tuple[str, str, str]:
    if not config.JIRA_BASE_URL:
        raise JiraUnavailable(
            "jira adapter requires JIRA_BASE_URL (e.g. https://yourorg.atlassian.net)"
        )
    if not config.JIRA_EMAIL:
        raise JiraUnavailable(
            "jira adapter requires JIRA_EMAIL (your Atlassian account email)"
        )
    if not config.JIRA_API_TOKEN:
        raise JiraUnavailable(
            "jira adapter requires JIRA_API_TOKEN. Create one at "
            "https://id.atlassian.com/manage-profile/security/api-tokens"
        )
    return config.JIRA_BASE_URL.rstrip("/"), config.JIRA_EMAIL, config.JIRA_API_TOKEN


def _request(path: str, params: dict | None = None) -> dict:
    """GET <base_url>/rest/api/3<path>?<params>. Tests monkeypatch this
    function to avoid live API calls."""
    base, email, token = _check_auth()
    creds = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")

    url = f"{base}{_API_PATH}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {creds}",
            "Accept": "application/json",
            "User-Agent": "mk-spec-master/jira-adapter",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise JiraUnavailable(
            f"JIRA API HTTP {exc.code}: {exc.reason}. "
            f"Check JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, and project access."
        ) from exc
    except urllib.error.URLError as exc:
        raise JiraUnavailable(f"JIRA API unreachable: {exc.reason}") from exc


# ---------- ADF → markdown ---------------------------------------------


def adf_to_markdown(adf) -> str:
    """Flatten an ADF document tree (or None / str) to markdown text.
    Handles the node types we see in 99% of JIRA descriptions; unknown
    nodes fall through with inner text preserved so we never drop data."""
    if adf is None:
        return ""
    if isinstance(adf, str):
        return adf

    def render(node) -> str:
        if isinstance(node, list):
            return "".join(render(n) for n in node)
        if not isinstance(node, dict):
            return ""

        typ = node.get("type", "")
        content = node.get("content") or []

        if typ == "text":
            return node.get("text", "")

        if typ == "doc":
            return "".join(render(c) for c in content)

        if typ == "heading":
            level = (node.get("attrs") or {}).get("level", 1)
            return f"\n{'#' * int(level)} {''.join(render(c) for c in content)}\n"

        if typ == "paragraph":
            return f"\n{''.join(render(c) for c in content)}\n"

        if typ == "bulletList":
            items = ["- " + render(c).strip() for c in content]
            return "\n".join(items) + "\n"

        if typ == "orderedList":
            items = [f"{i + 1}. " + render(c).strip() for i, c in enumerate(content)]
            return "\n".join(items) + "\n"

        if typ == "listItem":
            return "".join(render(c) for c in content)

        if typ == "codeBlock":
            return f"\n```\n{''.join(render(c) for c in content)}\n```\n"

        if typ == "hardBreak":
            return "\n"

        # Unknown node — render inner content best-effort.
        return "".join(render(c) for c in content)

    rendered = render(adf).strip()
    return rendered


# ---------- response parsing -------------------------------------------


def _summary_from_issue(issue: dict) -> SpecSummary:
    fields = issue.get("fields") or {}
    labels = fields.get("labels") or []
    if not isinstance(labels, list):
        labels = []
    return SpecSummary(
        id=str(issue.get("key", "")),
        title=str(fields.get("summary", "")),
        url=str(issue.get("self") or "").replace(_API_PATH + "/issue/", "/browse/"),
        status=((fields.get("status") or {}).get("name", "")),
        labels=[str(l) for l in labels],
    )


def _spec_from_issue(issue: dict, fallback_id: str = "") -> Spec:
    fields = issue.get("fields") or {}
    description = fields.get("description")
    body_md = adf_to_markdown(description)

    labels = fields.get("labels") or []
    if not isinstance(labels, list):
        labels = []

    return Spec(
        id=str(issue.get("key") or fallback_id),
        title=str(fields.get("summary", "")),
        body=body_md,
        url=str(issue.get("self") or "").replace(_API_PATH + "/issue/", "/browse/"),
        status=((fields.get("status") or {}).get("name", "")),
        labels=[str(l) for l in labels],
        metadata={
            "jira_id": issue.get("id", ""),
            "created": fields.get("created", ""),
            "updated": fields.get("updated", ""),
            "issue_type": ((fields.get("issuetype") or {}).get("name", "")),
        },
    )


# ---------- JQL helpers -------------------------------------------------


def _quote(value: str) -> str:
    """Quote a value for JQL — escape backslashes + double-quotes."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _build_jql(project_key: str, status: str | None, label: str | None) -> str:
    parts: list[str] = []
    if project_key:
        parts.append(f"project = {_quote(project_key)}")
    if status:
        parts.append(f"status = {_quote(status)}")
    if label:
        parts.append(f"labels = {_quote(label)}")
    if not parts:
        # JIRA's search endpoint requires *some* JQL — order-by alone works.
        return "ORDER BY updated DESC"
    return " AND ".join(parts) + " ORDER BY updated DESC"


# ---------- adapter -----------------------------------------------------


@register("jira")
class JiraAdapter(SpecSource):
    name = "jira"

    def list_specs(self, **filters) -> list[SpecSummary]:
        status_filter = filters.get("status")
        label_filter = filters.get("label")
        limit = int(filters.get("limit", 50))

        jql = _build_jql(config.SOURCE_KEY, status_filter, label_filter)
        payload = _request(
            "/search",
            {
                "jql": jql,
                "fields": "summary,status,labels",
                "maxResults": min(limit, 100),
            },
        )
        issues = payload.get("issues") or []

        out: list[SpecSummary] = []
        for issue in issues:
            out.append(_summary_from_issue(issue))
            if len(out) >= limit:
                break
        return out

    def fetch(self, spec_id: str) -> Spec:
        payload = _request(
            f"/issue/{spec_id}",
            {"fields": "summary,description,status,labels,created,updated,issuetype"},
        )
        if not payload or "key" not in payload:
            raise ValueError(
                f"jira: issue {spec_id!r} not found. Confirm the project "
                f"key prefix and API token access."
            )
        return _spec_from_issue(payload, fallback_id=spec_id)
