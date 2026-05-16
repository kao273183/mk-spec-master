"""Tests for the v0.3 finale: get_optimization_plan + spec-knowledge layer."""


def _isolate_index(tmp_path, monkeypatch):
    from mk_spec_master import config

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path / ".mk-spec-master")
    monkeypatch.setattr(config, "INDEX_PATH", tmp_path / ".mk-spec-master" / "index.json")


# ---------- get_optimization_plan ------------------------------------


def test_optimization_plan_empty_state_is_safe(tmp_path, monkeypatch):
    _isolate_index(tmp_path, monkeypatch)
    from mk_spec_master.tools.optimization import get_optimization_plan_tool

    result = get_optimization_plan_tool({})
    assert result["specs_total"] == 0
    assert "Optimization plan" in result["markdown"]
    assert "Layer 1" in result["markdown"]
    assert "Layer 2" in result["markdown"]
    assert "Layer 3" in result["markdown"]


def test_optimization_plan_layers_can_be_toggled(tmp_path, monkeypatch):
    _isolate_index(tmp_path, monkeypatch)
    from mk_spec_master.tools.optimization import get_optimization_plan_tool

    result = get_optimization_plan_tool({"include_coverage": False, "include_drift": False})
    assert "Layer 1" not in result["markdown"]
    assert "Layer 2" in result["markdown"]
    assert "Layer 3" not in result["markdown"]


def test_optimization_plan_surfaces_untested_specs(tmp_path, monkeypatch):
    _isolate_index(tmp_path, monkeypatch)

    from mk_spec_master.index import save_index
    save_index(
        {
            "version": 1,
            "specs": {
                "SPEC-UNTESTED": {"title": "Big feature, no tests", "linked_tests": []},
                "SPEC-OK": {
                    "title": "Already tested",
                    "linked_tests": [{"node_id": "t.py::test_one", "linked_at": "2026-01-01T00:00:00Z"}],
                },
            },
            "orphans": [],
        }
    )

    from mk_spec_master.tools.optimization import get_optimization_plan_tool

    result = get_optimization_plan_tool({"include_quality": False, "include_drift": False})
    assert result["untested_count"] == 1
    assert any(r["spec_id"] == "SPEC-UNTESTED" for r in result["untested"])
    assert "SPEC-UNTESTED" in result["markdown"]


# ---------- init_spec_knowledge --------------------------------------


def test_init_spec_knowledge_creates_file(tmp_path, monkeypatch):
    _isolate_index(tmp_path, monkeypatch)
    from mk_spec_master.tools.spec_knowledge import init_spec_knowledge_tool

    result = init_spec_knowledge_tool({"project_name": "my-app"})
    assert result["created"] is True

    path = tmp_path / "spec-knowledge.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "my-app" in content
    assert "EARS" in content
    assert "INVEST" in content


def test_init_spec_knowledge_refuses_to_overwrite_by_default(tmp_path, monkeypatch):
    _isolate_index(tmp_path, monkeypatch)
    from mk_spec_master.tools.spec_knowledge import init_spec_knowledge_tool

    (tmp_path / "spec-knowledge.md").write_text("# Existing\n", encoding="utf-8")

    result = init_spec_knowledge_tool({})
    assert result["created"] is False
    assert (tmp_path / "spec-knowledge.md").read_text(encoding="utf-8") == "# Existing\n"


def test_init_spec_knowledge_overwrite_replaces_file(tmp_path, monkeypatch):
    _isolate_index(tmp_path, monkeypatch)
    from mk_spec_master.tools.spec_knowledge import init_spec_knowledge_tool

    (tmp_path / "spec-knowledge.md").write_text("# Old\n", encoding="utf-8")
    result = init_spec_knowledge_tool({"overwrite": True})
    assert result["created"] is True
    assert "EARS" in (tmp_path / "spec-knowledge.md").read_text(encoding="utf-8")


# ---------- get_spec_context -----------------------------------------


def test_get_spec_context_uses_builtin_when_no_file(tmp_path, monkeypatch):
    _isolate_index(tmp_path, monkeypatch)
    from mk_spec_master.tools.spec_knowledge import get_spec_context_tool

    result = get_spec_context_tool({})
    assert result["source"] == "builtin"
    assert "EARS" in result["content"]


def test_get_spec_context_reads_file_when_present(tmp_path, monkeypatch):
    _isolate_index(tmp_path, monkeypatch)
    (tmp_path / "spec-knowledge.md").write_text(
        "# Spec knowledge — proj\n\n## Custom rules\n- TODO: stuff\n",
        encoding="utf-8",
    )

    from mk_spec_master.tools.spec_knowledge import get_spec_context_tool

    result = get_spec_context_tool({})
    assert result["source"] == "file"
    assert "Custom rules" in result["content"]


def test_get_spec_context_filters_by_section(tmp_path, monkeypatch):
    _isolate_index(tmp_path, monkeypatch)
    (tmp_path / "spec-knowledge.md").write_text(
        "# Spec knowledge\n\n## Actors\n- logged-in user\n- admin\n\n## Glossary\n- Order: a thing\n",
        encoding="utf-8",
    )

    from mk_spec_master.tools.spec_knowledge import get_spec_context_tool

    result = get_spec_context_tool({"section": "actors"})
    assert result["found"] is True
    assert "logged-in user" in result["content"]
    assert "Glossary" not in result["content"]
    assert "Order" not in result["content"]


def test_get_spec_context_returns_available_sections_when_not_found(tmp_path, monkeypatch):
    _isolate_index(tmp_path, monkeypatch)
    (tmp_path / "spec-knowledge.md").write_text(
        "# Title\n\n## A\n\n## B\n",
        encoding="utf-8",
    )

    from mk_spec_master.tools.spec_knowledge import get_spec_context_tool

    result = get_spec_context_tool({"section": "nope"})
    assert result["found"] is False
    assert "A" in result["available_sections"]
    assert "B" in result["available_sections"]
