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



# ---------- get_drift_report -------------------------------------------


def _set_tmp_project(tmp_path, monkeypatch):
    """Point SPECS_DIR and INDEX paths at a fresh tmp_path. Returns the
    specs subdir for writing fixture spec files."""
    from mk_spec_master import config

    specs_dir = tmp_path / "specs"
    index_dir = tmp_path / ".mk-spec-master"
    index_path = index_dir / "index.json"
    specs_dir.mkdir()

    monkeypatch.setattr(config, "SPECS_DIR", specs_dir)
    monkeypatch.setattr(config, "INDEX_DIR", index_dir)
    monkeypatch.setattr(config, "INDEX_PATH", index_path)

    # adapters.markdown_local imported SPECS_DIR at module load — re-patch
    # there too so list_specs / fetch read the new path.
    from mk_spec_master.adapters import markdown_local
    monkeypatch.setattr(markdown_local, "SPECS_DIR", specs_dir)
    return specs_dir


SPEC_V1 = """---
id: DRIFT-001
title: Sample
---

## Acceptance criteria
1. The user can log in
2. The user can log out
"""

SPEC_V1_PROSE_TWEAK = """---
id: DRIFT-001
title: Sample (re-worded intro)
---

This sentence rewords the lead-in but the AC list is identical.

## Acceptance criteria
1. The user can log in
2. The user can log out
"""

SPEC_V2_NEW_AC = """---
id: DRIFT-001
title: Sample
---

## Acceptance criteria
1. The user can log in
2. The user can log out
3. The user can reset their password
"""


def test_drift_fresh_when_hash_matches(tmp_path, monkeypatch):
    specs_dir = _set_tmp_project(tmp_path, monkeypatch)
    (specs_dir / "DRIFT-001.md").write_text(SPEC_V1, encoding="utf-8")

    from mk_spec_master.tools.specs import parse_spec_tool
    from mk_spec_master.tools.coverage import link_test_to_spec_tool, get_drift_report_tool

    parsed = parse_spec_tool({"spec_id": "DRIFT-001"})
    ac_hash = parsed["_meta"]["ac_hash"]
    assert ac_hash  # parse_spec exposes the hash

    link_test_to_spec_tool(
        {
            "spec_id": "DRIFT-001",
            "test_node_id": "tests/test_auth.py::test_login",
            "ac_hash": ac_hash,
        }
    )

    report = get_drift_report_tool({})
    assert report["fresh_count"] == 1
    assert report["drifted_count"] == 0


def test_drift_ignores_prose_only_edits(tmp_path, monkeypatch):
    """Hashing only the AC block means rewording the surrounding prose
    must not flag drift — that's the whole point of canonical hashing."""
    specs_dir = _set_tmp_project(tmp_path, monkeypatch)
    (specs_dir / "DRIFT-001.md").write_text(SPEC_V1, encoding="utf-8")

    from mk_spec_master.tools.specs import parse_spec_tool
    from mk_spec_master.tools.coverage import link_test_to_spec_tool, get_drift_report_tool

    parsed = parse_spec_tool({"spec_id": "DRIFT-001"})
    link_test_to_spec_tool(
        {"spec_id": "DRIFT-001", "test_node_id": "tests/x.py::t", "ac_hash": parsed["_meta"]["ac_hash"]}
    )

    (specs_dir / "DRIFT-001.md").write_text(SPEC_V1_PROSE_TWEAK, encoding="utf-8")

    report = get_drift_report_tool({})
    assert report["fresh_count"] == 1
    assert report["drifted_count"] == 0


def test_drift_flags_new_ac(tmp_path, monkeypatch):
    specs_dir = _set_tmp_project(tmp_path, monkeypatch)
    (specs_dir / "DRIFT-001.md").write_text(SPEC_V1, encoding="utf-8")

    from mk_spec_master.tools.specs import parse_spec_tool
    from mk_spec_master.tools.coverage import link_test_to_spec_tool, get_drift_report_tool

    parsed = parse_spec_tool({"spec_id": "DRIFT-001"})
    link_test_to_spec_tool(
        {"spec_id": "DRIFT-001", "test_node_id": "tests/x.py::t", "ac_hash": parsed["_meta"]["ac_hash"]}
    )

    # Add a new AC — drift expected.
    (specs_dir / "DRIFT-001.md").write_text(SPEC_V2_NEW_AC, encoding="utf-8")

    report = get_drift_report_tool({})
    assert report["drifted_count"] == 1
    assert report["fresh_count"] == 0
    assert report["drifted"][0]["spec_id"] == "DRIFT-001"
    assert "may be stale" in report["markdown"] or "Drifted" in report["markdown"]


def test_drift_unknown_when_no_hash_stored(tmp_path, monkeypatch):
    specs_dir = _set_tmp_project(tmp_path, monkeypatch)
    (specs_dir / "DRIFT-001.md").write_text(SPEC_V1, encoding="utf-8")

    from mk_spec_master.tools.coverage import link_test_to_spec_tool, get_drift_report_tool

    # Link without ac_hash — emulates v0.1-era data or a client that
    # didn't compute the hash.
    link_test_to_spec_tool({"spec_id": "DRIFT-001", "test_node_id": "tests/x.py::t"})

    report = get_drift_report_tool({})
    assert report["unknown_count"] == 1
    assert report["drifted_count"] == 0
    assert "Unknown" in report["markdown"]


def test_drift_stranded_when_source_missing(tmp_path, monkeypatch):
    _set_tmp_project(tmp_path, monkeypatch)
    # Do not write any spec file. Linking with ac_hash for a non-existent
    # spec means get_drift_report can't fetch it → stranded.

    from mk_spec_master.tools.coverage import link_test_to_spec_tool, get_drift_report_tool

    link_test_to_spec_tool(
        {"spec_id": "GHOST-999", "test_node_id": "tests/x.py::t", "ac_hash": "deadbeef" * 8}
    )

    report = get_drift_report_tool({})
    assert report["stranded_count"] == 1
    assert report["fresh_count"] == 0
    assert report["stranded"][0]["spec_id"] == "GHOST-999"


def test_compute_ac_hash_stable_and_unique():
    from mk_spec_master.tools.specs import compute_ac_hash

    # Same AC list → identical hash, even with surrounding prose changes.
    h1 = compute_ac_hash(SPEC_V1.split("---", 2)[2])
    h2 = compute_ac_hash(SPEC_V1_PROSE_TWEAK.split("---", 2)[2])
    assert h1 == h2

    # New AC → different hash.
    h3 = compute_ac_hash(SPEC_V2_NEW_AC.split("---", 2)[2])
    assert h3 != h1
