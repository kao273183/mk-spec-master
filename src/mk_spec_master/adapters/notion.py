"""Adapter for Notion (notion.so) databases.

Env:
    SPEC_SOURCE=notion
    NOTION_TOKEN=secret_XXX            Internal-integration token. Create one
                                        at https://www.notion.so/my-integrations
                                        then share the spec database with the
                                        integration via the database's "..."
                                        menu → Add connections.
    SPEC_PROJECT_KEY=<database-id>     The Notion database ID containing
                                        specs (32-char UUID, hyphens optional).

Spec id format: the Notion page UUID. Not human-friendly but stable;
custom "Key" / "ID" properties are exposed in metadata so users see
them, but we don't use them for lookup in v0.3.

Body field: Notion stores page content as a tree of typed blocks. We
flatten the supported block types (paragraph / headings / bulleted +
numbered lists / to_do / code) to markdown so the existing parse_spec
heuristics work. Unknown block types fall through with their inner
text preserved.

Zero new deps — stdlib urllib + base64.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from .. import config
from . import register
from .base import Spec, SpecSource, SpecSummary


class NotionUnavailable(RuntimeError):
    """Raised when the Notion API call fails or env vars are missing.
    Message is shown to the AI client; keep it actionable."""


_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"
_TIMEOUT_S = 20


# ---------- HTTP -------------------------------------------------------


def _check_auth() -> str:
    if not config.NOTION_TOKEN:
        raise NotionUnavailable(
            "notion adapter requires NOTION_TOKEN. Create an internal "
            "integration at https://www.notion.so/my-integrations, then "
            "share the spec database with that integration."
        )
    return config.NOTION_TOKEN


def _request(method: str, path: str, body: dict | None = None) -> dict:
    """Call the Notion REST API. Tests monkeypatch this to skip the network."""
    token = _check_auth()
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{_API_BASE}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
            "User-Agent": "mk-spec-master/notion-adapter",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise NotionUnavailable(
            f"Notion API HTTP {exc.code}: {exc.reason}. "
            f"Check NOTION_TOKEN, database ID, and integration sharing."
        ) from exc
    except urllib.error.URLError as exc:
        raise NotionUnavailable(f"Notion API unreachable: {exc.reason}") from exc


# ---------- block tree → markdown -------------------------------------


def _rich_text(rt_list: list) -> str:
    """Join Notion rich_text items' plain_text into a single string."""
    if not isinstance(rt_list, list):
        return ""
    return "".join(item.get("plain_text", "") for item in rt_list if isinstance(item, dict))


def blocks_to_markdown(blocks: list) -> str:
    """Flatten a list of Notion blocks to markdown.

    Notion's API doesn't number ordered-list items (each is just
    numbered_list_item); we restart numbering whenever a non-numbered
    block breaks the streak. parse_spec only needs `^\\d+\\.` to detect
    AC items, so the exact numbers don't matter — but sequential
    numbering is friendlier when the markdown is shown to a human."""
    if not isinstance(blocks, list):
        return ""

    lines: list[str] = []
    numbered_streak = 0
    for block in blocks:
        if not isinstance(block, dict):
            continue
        typ = block.get("type", "")
        data = block.get(typ) or {}
        text = _rich_text(data.get("rich_text") or [])

        if typ != "numbered_list_item":
            numbered_streak = 0

        if typ == "heading_1":
            lines.append(f"# {text}")
        elif typ == "heading_2":
            lines.append(f"## {text}")
        elif typ == "heading_3":
            lines.append(f"### {text}")
        elif typ == "paragraph":
            lines.append(text)
        elif typ == "bulleted_list_item":
            lines.append(f"- {text}")
        elif typ == "numbered_list_item":
            numbered_streak += 1
            lines.append(f"{numbered_streak}. {text}")
        elif typ == "to_do":
            checked = bool(data.get("checked"))
            mark = "[x]" if checked else "[ ]"
            lines.append(f"- {mark} {text}")
        elif typ == "code":
            lang = data.get("language") or ""
            lines.append(f"```{lang}\n{text}\n```")
        elif typ == "quote":
            lines.append(f"> {text}")
        else:
            # Unknown block — preserve any text we can extract.
            if text:
                lines.append(text)

    return "\n\n".join(line for line in lines if line is not None)


# ---------- page property extraction ----------------------------------


def _extract_title(page: dict) -> str:
    """Find the `title`-typed property on the page and join its rich text."""
    props = page.get("properties") or {}
    for _, prop in props.items():
        if isinstance(prop, dict) and prop.get("type") == "title":
            return _rich_text(prop.get("title") or [])
    return ""


def _extract_status(page: dict) -> str:
    """Best-effort status extraction. Matches common property shapes."""
    props = page.get("properties") or {}
    for name, prop in props.items():
        if not isinstance(prop, dict):
            continue
        if name.lower() not in {"status", "state"}:
            continue
        if prop.get("type") == "status":
            return ((prop.get("status") or {}).get("name") or "")
        if prop.get("type") == "select":
            return ((prop.get("select") or {}).get("name") or "")
    return ""


def _extract_labels(page: dict) -> list[str]:
    """Best-effort label extraction from multi_select properties named
    'Tags' / 'Labels'."""
    props = page.get("properties") or {}
    for name, prop in props.items():
        if not isinstance(prop, dict):
            continue
        if name.lower() not in {"tags", "labels"}:
            continue
        if prop.get("type") == "multi_select":
            return [opt.get("name", "") for opt in (prop.get("multi_select") or []) if isinstance(opt, dict)]
    return []


def _extract_custom_key(page: dict) -> str:
    """If the database has a rich_text or unique_id property named 'Key'
    or 'ID', return it — exposed via metadata so users see their
    human-friendly spec identifier even though we key off the page UUID."""
    props = page.get("properties") or {}
    for name, prop in props.items():
        if not isinstance(prop, dict):
            continue
        if name.lower() not in {"key", "id", "spec id", "spec_id"}:
            continue
        typ = prop.get("type")
        if typ == "rich_text":
            return _rich_text(prop.get("rich_text") or [])
        if typ == "unique_id":
            uid = prop.get("unique_id") or {}
            prefix = uid.get("prefix") or ""
            num = uid.get("number")
            return f"{prefix}-{num}" if prefix and num is not None else str(num or "")
        if typ == "title":
            return _rich_text(prop.get("title") or [])
    return ""


def _summary_from_page(page: dict) -> SpecSummary:
    return SpecSummary(
        id=str(page.get("id", "")),
        title=_extract_title(page),
        url=str(page.get("url") or ""),
        status=_extract_status(page),
        labels=_extract_labels(page),
    )


def _spec_from_page(page: dict, body_md: str, fallback_id: str = "") -> Spec:
    return Spec(
        id=str(page.get("id") or fallback_id),
        title=_extract_title(page),
        body=body_md,
        url=str(page.get("url") or ""),
        status=_extract_status(page),
        labels=_extract_labels(page),
        metadata={
            "custom_key": _extract_custom_key(page),
            "created_time": page.get("created_time", ""),
            "last_edited_time": page.get("last_edited_time", ""),
        },
    )


# ---------- adapter ----------------------------------------------------


def _database_id() -> str:
    if not config.SOURCE_KEY:
        raise NotionUnavailable(
            "notion adapter requires SPEC_PROJECT_KEY=<database-id>. "
            "Open the Notion database in the browser; the 32-char UUID "
            "in the URL is the database id."
        )
    return config.SOURCE_KEY


@register("notion")
class NotionAdapter(SpecSource):
    name = "notion"

    def list_specs(self, **filters) -> list[SpecSummary]:
        db_id = _database_id()
        limit = int(filters.get("limit", 50))

        # The /query endpoint supports filters but they need to know the
        # property names + types per database. For v0.3 we list everything
        # and let the caller filter client-side via list_specs(**filters).
        # Status / label filters get applied after we have summaries.
        body: dict = {"page_size": min(limit, 100)}
        payload = _request("POST", f"/databases/{db_id}/query", body)
        results = payload.get("results") or []

        status_filter = filters.get("status")
        label_filter = filters.get("label")

        out: list[SpecSummary] = []
        for page in results:
            if not isinstance(page, dict):
                continue
            summary = _summary_from_page(page)
            if status_filter and summary.status != status_filter:
                continue
            if label_filter and label_filter not in summary.labels:
                continue
            out.append(summary)
            if len(out) >= limit:
                break
        return out

    def fetch(self, spec_id: str) -> Spec:
        page = _request("GET", f"/pages/{spec_id}")
        if not page or page.get("object") != "page":
            raise ValueError(
                f"notion: page {spec_id!r} not found or not shared with "
                f"the integration."
            )

        children = _request("GET", f"/blocks/{spec_id}/children?page_size=100")
        blocks = children.get("results") or []
        body_md = blocks_to_markdown(blocks)
        return _spec_from_page(page, body_md, fallback_id=spec_id)
