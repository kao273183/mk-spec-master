"""Adapter for Figma files.

Env:
    SPEC_SOURCE=figma
    FIGMA_TOKEN=figd_XXX               Personal access token from
                                        Figma → Settings → Account →
                                        Personal access tokens.
    SPEC_PROJECT_KEY=<file-key>        File key from the file URL
                                        (https://figma.com/file/<KEY>/...).

Design decision: top-level frames are treated as specs. Each spec is
one screen / one feature / one flow — which matches how most product
teams structure design files (one frame per state).

Body extraction:
    1. Walk the frame's subtree collecting TEXT nodes, joined in
       document order. Headings written as `# Frame name` followed by
       the text content.
    2. Append a `## Comments` section at the end aggregating all
       comments anchored to nodes inside this frame's subtree.

Designers who write AC as text inside the frame (sticky-note style) OR
as Figma comments both end up in the body — and parse_spec's heading /
list-item heuristics pick them up automatically if they're formatted
as numbered or bulleted text. Free-form prose still flows through to
the AI client for interpretation.

Zero new deps — stdlib urllib.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from .. import config
from . import register
from .base import Spec, SpecSource, SpecSummary


class FigmaUnavailable(RuntimeError):
    """Raised when the Figma API call fails or env vars are missing.
    Message is shown to the AI client; keep it actionable."""


_API_BASE = "https://api.figma.com/v1"
_TIMEOUT_S = 20


# ---------- HTTP -------------------------------------------------------


def _check_auth() -> str:
    if not config.FIGMA_TOKEN:
        raise FigmaUnavailable(
            "figma adapter requires FIGMA_TOKEN. Generate one at "
            "https://www.figma.com/settings (Account → Personal access tokens)."
        )
    return config.FIGMA_TOKEN


def _request(path: str, params: dict | None = None) -> dict:
    """GET /v1<path>?<params>. Tests monkeypatch this to skip the network.

    Figma's auth header is `X-Figma-Token`, not `Authorization` — easy
    one to get wrong.
    """
    token = _check_auth()
    url = f"{_API_BASE}{path}"
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "X-Figma-Token": token,
            "Accept": "application/json",
            "User-Agent": "mk-spec-master/figma-adapter",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise FigmaUnavailable(
            f"Figma API HTTP {exc.code}: {exc.reason}. "
            f"Check FIGMA_TOKEN, file key, and your access to the file."
        ) from exc
    except urllib.error.URLError as exc:
        raise FigmaUnavailable(f"Figma API unreachable: {exc.reason}") from exc


def _file_key() -> str:
    if not config.SOURCE_KEY:
        raise FigmaUnavailable(
            "figma adapter requires SPEC_PROJECT_KEY=<file-key>. The file "
            "key is the segment between /file/ and the next slash in the "
            "Figma file URL."
        )
    return config.SOURCE_KEY


# ---------- node tree → markdown --------------------------------------


def _collect_node_ids(node: dict, out: set[str]) -> None:
    """Walk the subtree gathering every node id — used to filter
    comments that anchor onto any descendant of the frame."""
    nid = node.get("id")
    if isinstance(nid, str):
        out.add(nid)
    for child in node.get("children") or []:
        if isinstance(child, dict):
            _collect_node_ids(child, out)


def _extract_text(node: dict) -> str:
    """Depth-first walk concatenating TEXT node characters."""
    parts: list[str] = []
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "TEXT":
        text = node.get("characters", "")
        if text:
            parts.append(text)
    for child in node.get("children") or []:
        chunk = _extract_text(child)
        if chunk:
            parts.append(chunk)
    return "\n".join(parts)


def _comments_for_subtree(comments: list, node_ids: set[str]) -> list[dict]:
    """Return comments anchored to any node id in the subtree set.
    Comments without an anchor (file-level) are returned only if the
    subtree contains the document root — too noisy otherwise."""
    out = []
    for c in comments or []:
        if not isinstance(c, dict):
            continue
        anchor = (c.get("client_meta") or {}).get("node_id")
        if anchor and anchor in node_ids:
            out.append(c)
    return out


def _format_comments(comments: list) -> str:
    if not comments:
        return ""
    lines = ["", "## Comments", ""]
    for c in comments:
        user = (c.get("user") or {}).get("handle") or "anonymous"
        message = (c.get("message") or "").strip()
        if message:
            lines.append(f"- **{user}**: {message}")
    return "\n".join(lines)


# ---------- summary / spec construction --------------------------------


def _summary_from_frame(file_key: str, frame: dict) -> SpecSummary:
    return SpecSummary(
        id=str(frame.get("id", "")),
        title=str(frame.get("name", "")),
        url=f"https://www.figma.com/file/{file_key}/?node-id={urllib.parse.quote(frame.get('id', ''))}",
        status="",   # Figma frames have no status concept
        labels=[],
    )


def _spec_from_frame(file_key: str, frame: dict, body_md: str) -> Spec:
    return Spec(
        id=str(frame.get("id", "")),
        title=str(frame.get("name", "")),
        body=body_md,
        url=f"https://www.figma.com/file/{file_key}/?node-id={urllib.parse.quote(frame.get('id', ''))}",
        status="",
        labels=[],
        metadata={
            "figma_node_type": frame.get("type", ""),
        },
    )


# ---------- adapter ----------------------------------------------------


@register("figma")
class FigmaAdapter(SpecSource):
    name = "figma"

    def list_specs(self, **filters) -> list[SpecSummary]:
        file_key = _file_key()
        limit = int(filters.get("limit", 50))

        # depth=2: gives us pages (CANVAS) and their top-level frames
        # without walking deep into every layer.
        data = _request(f"/files/{file_key}", {"depth": 2})
        document = data.get("document") or {}

        out: list[SpecSummary] = []
        for page in document.get("children") or []:
            if not isinstance(page, dict):
                continue
            for child in page.get("children") or []:
                if not isinstance(child, dict):
                    continue
                # Only FRAME and COMPONENT_SET sit at the screen level in
                # most product files. SECTION is sometimes used as a
                # container — skip it (its children are the real frames).
                if child.get("type") not in {"FRAME", "COMPONENT_SET"}:
                    continue
                out.append(_summary_from_frame(file_key, child))
                if len(out) >= limit:
                    return out
        return out

    def fetch(self, spec_id: str) -> Spec:
        file_key = _file_key()
        nodes_response = _request(f"/files/{file_key}/nodes", {"ids": spec_id, "depth": 10})
        node_record = (nodes_response.get("nodes") or {}).get(spec_id)
        if not node_record:
            raise ValueError(
                f"figma: node {spec_id!r} not found in file {file_key!r}. "
                f"Confirm the frame id and file access."
            )
        document = node_record.get("document") or {}

        # 1. Collect text from the subtree as the spec body.
        text_body = _extract_text(document)
        title_line = f"# {document.get('name', '')}\n\n" if document.get("name") else ""

        # 2. Layer in any comments anchored to nodes inside the subtree.
        comments_response = _request(f"/files/{file_key}/comments")
        comments_all = comments_response.get("comments") or []
        node_ids: set[str] = set()
        _collect_node_ids(document, node_ids)
        relevant = _comments_for_subtree(comments_all, node_ids)
        comments_md = _format_comments(relevant)

        body_md = (title_line + text_body + comments_md).strip()
        return _spec_from_frame(file_key, document, body_md)
