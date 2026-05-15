"""Coverage tools — write to the traceability index.

v0.1 ships just link_test_to_spec (manual linking). get_coverage_matrix and
get_drift_report arrive in v0.2 once we have real coverage data from
mk-qa-master to play against.
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

    index = load_index()
    specs = index.setdefault("specs", {})
    entry = specs.setdefault(str(spec_id), {
        "linked_tests": [],
    })
    entry.setdefault("linked_tests", [])

    # De-dupe by node_id; updating updates the timestamp.
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
