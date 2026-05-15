"""Smoke tests — exercise every v0.1 tool end-to-end against the shipped
examples/specs/SPEC-001 corpus.

These don't go through the MCP transport; they call the tool functions
directly. That keeps the harness simple and the failures legible. The
transport itself is exercised by Glama / Smithery sandbox introspection.
"""

import pytest


# ---------- list_specs -------------------------------------------------


def test_list_specs_returns_spec_001():
    from mk_spec_master.tools.specs import list_specs_tool

    result = list_specs_tool({})

    assert result["source"] == "markdown_local"
    assert result["count"] >= 1
    ids = [s["id"] for s in result["specs"]]
    assert "SPEC-001" in ids


def test_list_specs_status_filter_excludes_nonmatching():
    from mk_spec_master.tools.specs import list_specs_tool

    # SPEC-001 has status "in-progress" — filter by something else, expect zero.
    result = list_specs_tool({"status": "nonexistent-status-zzz"})
    assert result["count"] == 0


# ---------- fetch_spec -------------------------------------------------


def test_fetch_spec_returns_full_record():
    from mk_spec_master.tools.specs import fetch_spec_tool

    spec = fetch_spec_tool({"spec_id": "SPEC-001"})

    assert spec["id"] == "SPEC-001"
    assert "discount" in spec["title"].lower()
    assert "Acceptance criteria" in spec["body"]
    assert "checkout" in spec["labels"]


def test_fetch_spec_missing_id_returns_error():
    from mk_spec_master.tools.specs import fetch_spec_tool

    result = fetch_spec_tool({})
    assert "error" in result


# ---------- parse_spec -------------------------------------------------


def test_parse_spec_finds_four_acceptance_criteria():
    from mk_spec_master.tools.specs import parse_spec_tool

    result = parse_spec_tool({"spec_id": "SPEC-001"})

    assert result["_meta"]["ac_block_found"] is True
    assert len(result["acceptance_criteria"]) == 4
    # IDs should be ac-1 .. ac-4 in order.
    assert [ac["id"] for ac in result["acceptance_criteria"]] == [
        "ac-1", "ac-2", "ac-3", "ac-4",
    ]


def test_parse_spec_with_raw_text_skips_adapter():
    from mk_spec_master.tools.specs import parse_spec_tool

    raw = (
        "# Some spec\n\n"
        "## Acceptance criteria\n"
        "1. First criterion\n"
        "2. Second criterion\n"
    )
    result = parse_spec_tool({"raw_text": raw})
    assert len(result["acceptance_criteria"]) == 2


# ---------- extract_scenarios -----------------------------------------


def test_extract_scenarios_classifies_kinds():
    """SPEC-001: AC1 = happy (valid code), AC2-4 = error variants."""
    from mk_spec_master.tools.specs import parse_spec_tool
    from mk_spec_master.tools.scenarios import extract_scenarios_tool

    parsed = parse_spec_tool({"spec_id": "SPEC-001"})
    result = extract_scenarios_tool(
        {"acceptance_criteria": parsed["acceptance_criteria"]}
    )

    assert result["count"] == 4
    kinds = [s["kind"] for s in result["scenarios"]]
    assert kinds.count("happy") >= 1
    assert kinds.count("error") >= 2


def test_extract_scenarios_handles_empty_input():
    from mk_spec_master.tools.scenarios import extract_scenarios_tool

    result = extract_scenarios_tool({"acceptance_criteria": []})
    assert result == {"count": 0, "scenarios": []}


# ---------- generate_test_plan ----------------------------------------


def test_generate_test_plan_emits_handoff_block_per_scenario():
    from mk_spec_master.tools.scenarios import generate_test_plan_tool

    result = generate_test_plan_tool({"spec_id": "SPEC-001"})

    assert result["scenario_count"] == 4
    # Each scenario should produce one business_context handoff block.
    assert result["markdown"].count("business_context: |") == 4
    assert "Test plan — " in result["markdown"]


# ---------- link_test_to_spec -----------------------------------------


def test_link_test_to_spec_writes_index(tmp_path, monkeypatch):
    from mk_spec_master import config

    monkeypatch.setattr(config, "INDEX_DIR", tmp_path / ".mk-spec-master")
    monkeypatch.setattr(config, "INDEX_PATH", tmp_path / ".mk-spec-master" / "index.json")

    from mk_spec_master.tools.coverage import link_test_to_spec_tool

    first = link_test_to_spec_tool(
        {"spec_id": "SPEC-001", "test_node_id": "tests/test_checkout.py::test_apply_discount"}
    )
    assert first["action"] == "added"
    assert first["total_links_for_spec"] == 1

    # Re-link same node — should update, not duplicate.
    second = link_test_to_spec_tool(
        {"spec_id": "SPEC-001", "test_node_id": "tests/test_checkout.py::test_apply_discount"}
    )
    assert second["action"] == "updated"
    assert second["total_links_for_spec"] == 1

    # Different node — new link.
    third = link_test_to_spec_tool(
        {"spec_id": "SPEC-001", "test_node_id": "tests/test_checkout.py::test_invalid_promo"}
    )
    assert third["action"] == "added"
    assert third["total_links_for_spec"] == 2

    # Index file should exist with both entries.
    import json

    written = json.loads((tmp_path / ".mk-spec-master" / "index.json").read_text())
    assert len(written["specs"]["SPEC-001"]["linked_tests"]) == 2


# ---------- server tool dispatch (lightweight) -------------------------


def test_server_dispatch_table_covers_all_seven_tools():
    """If a tool name is added to the list_tools schema, dispatch must also
    have it. This catches the easy 'forgot to wire it up' mistake."""
    import asyncio

    from mk_spec_master.server import _DISPATCH, list_tools

    declared = {t.name for t in asyncio.run(list_tools())}
    dispatched = set(_DISPATCH.keys())

    assert declared == dispatched, (
        f"declared - dispatched = {declared - dispatched}; "
        f"dispatched - declared = {dispatched - declared}"
    )
    assert len(declared) == 10  # v0.2: original 7 + coverage_matrix + analyze + propose
