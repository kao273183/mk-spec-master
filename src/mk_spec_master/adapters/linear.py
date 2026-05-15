"""Adapter for Linear (linear.app).

Env:
    SPEC_SOURCE=linear
    LINEAR_API_KEY=lin_api_XXX        Personal API key — Settings → API
    SPEC_PROJECT_KEY=ENG              Team key (optional). If unset, lists
                                       across every team the API key can see.

Auth: Linear personal API keys go in the Authorization header verbatim
— **no `Bearer` prefix**. (OAuth tokens do use `Bearer`, but personal
keys are simpler for solo / small-team installs and this adapter
targets that path.)

Spec id format: Linear's human identifier ("ENG-123") is used as the
spec_id. The internal UUID is kept in `metadata.linear_id` for
debugging but isn't exposed elsewhere.

Networking: uses stdlib urllib so the package stays mcp-only on the
dependency side. GraphQL POSTs are small JSON (<5kB) — the 20s timeout
is generous, and request errors surface as LinearUnavailable with the
underlying message preserved.
"""

import json
import urllib.error
import urllib.request

from .. import config
from . import register
from .base import Spec, SpecSource, SpecSummary


class LinearUnavailable(RuntimeError):
    """Raised when the Linear API call fails. Message is propagated to
    the AI client; keep it actionable."""


_API_URL = "https://api.linear.app/graphql"
_TIMEOUT_S = 20


def _check_auth() -> str:
    api_key = config.LINEAR_API_KEY
    if not api_key:
        raise LinearUnavailable(
            "linear adapter requires LINEAR_API_KEY. Generate a personal "
            "API key at https://linear.app/settings/api and set it as an "
            "env var on this MCP server."
        )
    return api_key


def _gql(query: str, variables: dict | None = None) -> dict:
    """POST a GraphQL query and return the `data` dict. Tests monkeypatch
    this function to skip the network."""
    api_key = _check_auth()
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(
        _API_URL,
        data=payload,
        headers={
            "Authorization": api_key,
            "Content-Type": "application/json",
            "User-Agent": "mk-spec-master/linear-adapter",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            response = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise LinearUnavailable(
            f"Linear API HTTP {exc.code}: {exc.reason}. "
            f"Check LINEAR_API_KEY and team access."
        ) from exc
    except urllib.error.URLError as exc:
        raise LinearUnavailable(f"Linear API unreachable: {exc.reason}") from exc

    if response.get("errors"):
        msg = "; ".join(e.get("message", "?") for e in response["errors"])
        raise LinearUnavailable(f"Linear API errors: {msg}")
    return response.get("data") or {}


_LIST_QUERY = """
query Issues($filter: IssueFilter, $first: Int!) {
  issues(filter: $filter, first: $first) {
    nodes {
      id
      identifier
      title
      state { name }
      labels { nodes { name } }
      url
    }
  }
}
"""

_FETCH_QUERY = """
query IssueByIdentifier($id: String!) {
  issueByIdentifier(id: $id) {
    id
    identifier
    title
    description
    state { name }
    labels { nodes { name } }
    url
    createdAt
    updatedAt
  }
}
"""


def _summary_from_node(node: dict) -> SpecSummary:
    labels = [
        lbl.get("name", "")
        for lbl in (node.get("labels") or {}).get("nodes", []) or []
        if isinstance(lbl, dict)
    ]
    return SpecSummary(
        id=node.get("identifier", ""),
        title=node.get("title", ""),
        url=node.get("url", ""),
        status=(node.get("state") or {}).get("name", ""),
        labels=labels,
    )


def _spec_from_node(node: dict, fallback_id: str = "") -> Spec:
    labels = [
        lbl.get("name", "")
        for lbl in (node.get("labels") or {}).get("nodes", []) or []
        if isinstance(lbl, dict)
    ]
    return Spec(
        id=node.get("identifier") or fallback_id,
        title=node.get("title", ""),
        body=node.get("description") or "",
        url=node.get("url", ""),
        status=(node.get("state") or {}).get("name", ""),
        labels=labels,
        metadata={
            "linear_id": node.get("id", ""),
            "created_at": node.get("createdAt", ""),
            "updated_at": node.get("updatedAt", ""),
        },
    )


@register("linear")
class LinearAdapter(SpecSource):
    name = "linear"

    def list_specs(self, **filters) -> list[SpecSummary]:
        status_filter = filters.get("status")
        label_filter = filters.get("label")
        limit = int(filters.get("limit", 50))

        gql_filter: dict = {}
        team_key = config.SOURCE_KEY
        if team_key:
            gql_filter["team"] = {"key": {"eq": team_key}}
        if status_filter:
            gql_filter["state"] = {"name": {"eq": status_filter}}
        if label_filter:
            gql_filter["labels"] = {"name": {"eq": label_filter}}

        # `first` is a Linear API cap (max 250 per page); fewer is fine.
        data = _gql(_LIST_QUERY, {"filter": gql_filter, "first": min(limit, 250)})
        nodes = (data.get("issues") or {}).get("nodes") or []

        out: list[SpecSummary] = []
        for n in nodes:
            out.append(_summary_from_node(n))
            if len(out) >= limit:
                break
        return out

    def fetch(self, spec_id: str) -> Spec:
        data = _gql(_FETCH_QUERY, {"id": spec_id})
        issue = data.get("issueByIdentifier")
        if not issue:
            raise ValueError(
                f"linear: issue {spec_id!r} not found. Confirm the team "
                f"prefix matches SPEC_PROJECT_KEY and the API key has access."
            )
        return _spec_from_node(issue, fallback_id=spec_id)
