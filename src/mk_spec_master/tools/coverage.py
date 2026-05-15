"""Coverage tools — read/write the traceability index.

v0.1 shipped link_test_to_spec only. v0.2 adds get_coverage_matrix so
users can answer the killer question: "which specs have tests?".
"""

import datetime as _dt
from typing import Any

from ..index import load_index, save_index


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def link_test_to_spec_tool(arguments: dict) -> dict[str, Any]:
    spec_id = arguments.get("spec_id")
    test_node_id = arguments.get("test_node_id")
    if not spec_id or not test_node_id:
        return {"error": "spec_id and test_node_id are both required"}

    # Optional metadata — AI clients usually have these from list_specs /
    # fetch_spec earlier in the chain. Pass them in and the coverage
    # matrix renders titles without re-fetching from the source.
    spec_title = arguments.get("spec_title")
    spec_source = arguments.get("spec_source")
    spec_url = arguments.get("spec_url")

    index = load_index()
    specs = index.setdefault("specs", {})
    entry = specs.setdefault(str(spec_id), {"linked_tests": []})
    entry.setdefault("linked_tests", [])

    # Cache spec metadata into the index entry — never overwrite a stored
    # value with None, so partial calls don't blank out previously-known
    # titles.
    if spec_title:
        entry["title"] = spec_title
    if spec_source:
        entry["source"] = spec_source
    if spec_url:
        entry["url"] = spec_url
    entry.setdefault("last_synced", _now_iso())

    existing = next(
        (t for t in entry["linked_tests"] if t.get("node_id") == test_node_id),
        None,
    )
    if existing:
        existing["linked_at"] = _now_iso()
        action = "updated"
    else:
        entry["linked_tests"].append(
            {
                "node_id": str(test_node_id),
                "linked_at": _now_iso(),
                "last_status": "unknown",
                "last_run": "",
            }
        )
        action = "added"

    save_index(index)

    return {
        "action": action,
        "spec_id": spec_id,
        "test_node_id": test_node_id,
        "total_links_for_spec": len(entry["linked_tests"]),
    }


def get_coverage_matrix_tool(arguments: dict) -> dict[str, Any]:
    """Snapshot of every spec ↔ test link recorded so far.

    Args:
        min_tests: filter — only include specs with >= N linked tests (0 = all,
            useful for finding untested specs).
        include_orphans: bool, default True. Adds the orphans block to output.

    Returns a structured payload + a ready-to-paste markdown table.
    """
    min_tests = int(arguments.get("min_tests", 0))
    include_orphans = bool(arguments.get("include_orphans", True))

    index = load_index()
    specs: dict = index.get("specs", {}) or {}

    rows: list[dict] = []
    for spec_id, entry in specs.items():
        linked = entry.get("linked_tests") or []
        if len(linked) < min_tests:
            continue
        last_run = max((t.get("last_run") or "" for t in linked), default="")
        last_status = next(
            (t.get("last_status") for t in linked if t.get("last_run") == last_run and last_run),
            "—",
        )
        rows.append(
            {
                "spec_id": spec_id,
                "title": entry.get("title") or "",
                "source": entry.get("source") or "",
                "url": entry.get("url") or "",
                "tests_count": len(linked),
                "last_run": last_run,
                "last_status": last_status or "—",
                "linked_tests": linked,
            }
        )

    rows.sort(key=lambda r: (r["tests_count"], r["spec_id"]))

    md_lines = [
        "# Coverage matrix",
        "",
        f"- Specs tracked: {len(specs)}",
        f"- Specs shown (min_tests={min_tests}): {len(rows)}",
        f"- Specs with zero tests: {sum(1 for r in rows if r['tests_count'] == 0)}",
        "",
        "| Spec | Title | Tests | Last status |",
        "|---|---|---:|---|",
    ]
    for r in rows:
        title_cell = r["title"] or "_(no metadata)_"
        md_lines.append(
            f"| `{r['spec_id']}` | {title_cell} | {r['tests_count']} | {r['last_status']} |"
        )

    orphans = index.get("orphans") or []
    if include_orphans and orphans:
        md_lines += ["", "## Orphan tests", "", "Tests recorded without a linked spec:", ""]
        for o in orphans:
            md_lines.append(f"- `{o.get('test_node_id', '?')}`  *(first_seen: {o.get('first_seen', '?')})*")

    return {
        "specs_total": len(specs),
        "specs_shown": len(rows),
        "specs_untested": sum(1 for r in rows if r["tests_count"] == 0),
        "orphan_count": len(orphans),
        "rows": rows,
        "markdown": "\n".join(md_lines),
    }
