"""v0.2 smoke tests — coverage matrix + spec quality coach pair.

Most of these exercise tools through their public functions (not the MCP
transport) so failures point at logic, not protocol.
"""

import json


# ---------- get_coverage_matrix ----------------------------------------


def test_coverage_matrix_empty_index_is_safe(tmp_path, monkeypatch):
    from mk_spec_master import config
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path / ".mk-spec-master")
    monkeypatch.setattr(config, "INDEX_PATH", tmp_path / ".mk-spec-master" / "index.json")

    from mk_spec_master.tools.coverage import get_coverage_matrix_tool

    result = get_coverage_matrix_tool({})
    assert result["specs_total"] == 0
    assert result["rows"] == []
    assert "Coverage matrix" in result["markdown"]


def test_coverage_matrix_renders_linked_specs(tmp_path, monkeypatch):
    from mk_spec_master import config
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path / ".mk-spec-master")
    monkeypatch.setattr(config, "INDEX_PATH", tmp_path / ".mk-spec-master" / "index.json")

    from mk_spec_master.tools.coverage import (
        get_coverage_matrix_tool,
        link_test_to_spec_tool,
    )

    link_test_to_spec_tool(
        {
            "spec_id": "SPEC-001",
            "test_node_id": "tests/test_checkout.py::test_apply_discount",
            "spec_title": "Apply discount at checkout",
            "spec_source": "markdown_local",
        }
    )
    link_test_to_spec_tool(
        {
            "spec_id": "SPEC-001",
            "test_node_id": "tests/test_checkout.py::test_invalid_promo",
            "spec_title": "Apply discount at checkout",
        }
    )
    link_test_to_spec_tool(
        {
            "spec_id": "SPEC-099-untested",
            "test_node_id": "tests/test_orphan.py::test_dummy",
            "spec_title": "Untested example",
        }
    )

    result = get_coverage_matrix_tool({})
    assert result["specs_total"] == 2
    titles = {row["title"] for row in result["rows"]}
    assert "Apply discount at checkout" in titles

    spec1_row = next(r for r in result["rows"] if r["spec_id"] == "SPEC-001")
    assert spec1_row["tests_count"] == 2

    # Markdown table should include both spec rows + the section header.
    assert "SPEC-001" in result["markdown"]
    assert "Coverage matrix" in result["markdown"]


def test_coverage_matrix_min_tests_filter(tmp_path, monkeypatch):
    from mk_spec_master import config
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path / ".mk-spec-master")
    monkeypatch.setattr(config, "INDEX_PATH", tmp_path / ".mk-spec-master" / "index.json")

    from mk_spec_master.tools.coverage import (
        get_coverage_matrix_tool,
        link_test_to_spec_tool,
    )

    link_test_to_spec_tool(
        {"spec_id": "SPEC-A", "test_node_id": "tests/a.py::t1", "spec_title": "A"}
    )
    link_test_to_spec_tool(
        {"spec_id": "SPEC-A", "test_node_id": "tests/a.py::t2", "spec_title": "A"}
    )
    link_test_to_spec_tool(
        {"spec_id": "SPEC-B", "test_node_id": "tests/b.py::t1", "spec_title": "B"}
    )

    # min_tests=2 → only SPEC-A survives.
    result = get_coverage_matrix_tool({"min_tests": 2})
    assert result["specs_shown"] == 1
    assert result["rows"][0]["spec_id"] == "SPEC-A"


# ---------- analyze_spec_quality --------------------------------------


def test_analyze_spec_quality_flags_vague_terms():
    """English + Chinese vague terms both trigger."""
    from mk_spec_master.tools.quality import analyze_spec_quality_tool

    raw = (
        "# A spec\n\n"
        "## Acceptance criteria\n"
        "1. The page should load fast and feel intuitive\n"
        "2. 操作要簡單方便\n"
    )
    result = analyze_spec_quality_tool({"raw_text": raw})
    issues = {f["evidence"] for f in result["results"][0]["findings"]}

    assert "fast" in issues
    assert "intuitive" in issues
    assert "簡單" in issues or "方便" in issues


def test_analyze_spec_quality_flags_implementation_leak():
    from mk_spec_master.tools.quality import analyze_spec_quality_tool

    raw = (
        "# A spec\n\n"
        "## Acceptance criteria\n"
        "1. The system uses Redis to cache results\n"
        "2. 透過 Kafka 串接資料\n"
    )
    result = analyze_spec_quality_tool({"raw_text": raw})
    issues = [f["issue"] for f in result["results"][0]["findings"]]

    assert "untestable_implementation_ref" in issues


def test_analyze_spec_quality_flags_unclear_roles_without_preconditions():
    from mk_spec_master.tools.quality import analyze_spec_quality_tool

    raw = (
        "# A spec\n\n"
        "## Acceptance criteria\n"
        "1. A logged-in user can view their orders\n"
    )
    result = analyze_spec_quality_tool({"raw_text": raw})
    issues = [f["issue"] for f in result["results"][0]["findings"]]

    assert "unclear_role_refs" in issues


def test_analyze_spec_quality_clean_spec_scores_high():
    from mk_spec_master.tools.quality import analyze_spec_quality_tool

    raw = (
        "# Clean spec\n\n"
        "## Preconditions\n"
        "- An authenticated user with at least one order in history\n\n"
        "## Acceptance criteria\n"
        "1. The order list returns within 200ms p95 on the staging tier\n"
        "2. Each row displays the order number, date, and total price\n"
    )
    result = analyze_spec_quality_tool({"raw_text": raw})
    spec_result = result["results"][0]

    assert spec_result["finding_count"] == 0
    assert spec_result["score"] == 100


# ---------- propose_spec_improvements ---------------------------------


def test_propose_emits_coach_markdown_with_findings():
    from mk_spec_master.tools.quality import (
        analyze_spec_quality_tool,
        propose_spec_improvements_tool,
    )

    raw = (
        "# Spec\n\n"
        "## Acceptance criteria\n"
        "1. Page loads fast\n"
        "2. Uses Redis cache internally\n"
    )
    analysis = analyze_spec_quality_tool({"raw_text": raw})
    result = propose_spec_improvements_tool({"analysis": analysis})

    md = result["markdown"]
    assert "Spec quality coach" in md
    assert "Vague language" in md
    assert "Untestable" in md or "implementation" in md.lower()
    assert len(result["actions"]) >= 1


def test_propose_clean_spec_says_no_issues():
    from mk_spec_master.tools.quality import propose_spec_improvements_tool

    raw = (
        "# Clean spec\n\n"
        "## Preconditions\n"
        "- An authenticated user.\n\n"
        "## Acceptance criteria\n"
        "1. Response time under 200ms p95\n"
    )
    result = propose_spec_improvements_tool({"raw_text": raw})

    assert "No issues" in result["markdown"]
    assert result["actions"] == []
