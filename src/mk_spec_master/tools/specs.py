"""Spec-discovery + parsing tools.

list_specs / fetch_spec are thin wrappers over the active adapter.
parse_spec is the heuristic AC extractor — finds an "Acceptance criteria"
section heading and pulls numbered / bulleted items beneath it. Roles +
preconditions stay empty in v0.1; v0.2's spec-quality coach fills them.
"""

import hashlib
import re
from dataclasses import asdict
from typing import Any

from ..adapters import get_source
from ..config import SOURCE_NAME

# Match common heading variants. Case-insensitive, language-aware enough
# to cover en + zh-TW + zh-CN spec conventions. Extend in v0.2 as more
# spec corpora come in.
_AC_HEADING_RE = re.compile(
    r"""
    ^\s*\#{1,6}\s*
    (
        acceptance\s*criteria
      | acceptance\s*criterions
      | acceptance
      | ac
      | requirements
      | 驗收條件
      | 驗收標準
      | 验收条件
      | 验收标准
      | 需求
    )
    \s*:?\s*$
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)

# A list item — `1.`, `1)`, `-`, `*`. Stops at next heading or blank-line
# gap signaling end of the AC list section.
_LIST_ITEM_RE = re.compile(
    r"^\s*(?:\d+[.)]|-|\*)\s+(.+?)$",
    re.MULTILINE,
)


def _extract_ac_block(body: str) -> str:
    """Return the chunk of body between the AC heading and the next heading
    of equal-or-greater depth. If no AC heading found, returns ''."""
    m = _AC_HEADING_RE.search(body)
    if not m:
        return ""
    start = m.end()
    # Find the next heading after start.
    rest = body[start:]
    next_heading = re.search(r"^\s*\#{1,6}\s+\S", rest, re.MULTILINE)
    return rest[: next_heading.start()] if next_heading else rest


def _ac_items(block: str) -> list[str]:
    return [m.group(1).strip() for m in _LIST_ITEM_RE.finditer(block)]


def compute_ac_hash(body: str) -> str:
    """SHA-256 over the canonical (whitespace-normalised) AC list.

    Hash inputs deliberately exclude prose around the AC list so the
    drift signal isn't a false positive for unrelated edits (e.g.,
    rewriting the 'Context' or 'Notes for QA' section without touching
    the AC). If there's no AC heading at all, hash the full body.
    """
    ac_block = _extract_ac_block(body)
    items = _ac_items(ac_block)
    if items:
        canonical = "\n".join(item.strip() for item in items)
    else:
        canonical = body.strip()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def list_specs_tool(arguments: dict) -> dict:
    source = get_source(SOURCE_NAME)
    filters = {k: v for k, v in arguments.items() if v is not None}
    summaries = source.list_specs(**filters)
    return {
        "source": SOURCE_NAME,
        "count": len(summaries),
        "specs": [asdict(s) for s in summaries],
    }


def fetch_spec_tool(arguments: dict) -> dict[str, Any]:
    spec_id = arguments.get("spec_id") or arguments.get("id")
    if not spec_id:
        return {"error": "spec_id is required"}
    source = get_source(SOURCE_NAME)
    spec = source.fetch(str(spec_id))
    return asdict(spec)


def parse_spec_tool(arguments: dict) -> dict[str, Any]:
    """Either pass spec_id (uses the active adapter) or raw_text (offline mode)."""
    raw_text = arguments.get("raw_text")
    spec_id = arguments.get("spec_id") or arguments.get("id")

    if raw_text:
        title = ""
        body = raw_text
    elif spec_id:
        source = get_source(SOURCE_NAME)
        spec = source.fetch(str(spec_id))
        title = spec.title
        body = spec.body
    else:
        return {"error": "pass spec_id or raw_text"}

    ac_block = _extract_ac_block(body)
    items = _ac_items(ac_block)

    acceptance_criteria = [
        {"id": f"ac-{i + 1}", "text": text}
        for i, text in enumerate(items)
    ]

    return {
        "spec_id": spec_id or "",
        "title": title,
        "acceptance_criteria": acceptance_criteria,
        "roles": [],          # v0.2
        "preconditions": [],  # v0.2
        "_meta": {
            "ac_block_found": bool(ac_block.strip()),
            "ac_count": len(acceptance_criteria),
            "ac_hash": compute_ac_hash(body),
        },
    }
