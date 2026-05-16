"""Tests for auto_link_tests — scan tmp dirs of fixture test files and
assert correct discovery / linking behaviour."""

import json
import textwrap


def _set_tmp_index(tmp_path, monkeypatch):
    from mk_spec_master import config

    monkeypatch.setattr(config, "INDEX_DIR", tmp_path / ".mk-spec-master")
    monkeypatch.setattr(config, "INDEX_PATH", tmp_path / ".mk-spec-master" / "index.json")


def _write(p, content):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content), encoding="utf-8")


# ---------- Python ---------------------------------------------------


def test_auto_link_finds_python_docstring_and_comment_tags(tmp_path, monkeypatch):
    _set_tmp_index(tmp_path, monkeypatch)
    test_dir = tmp_path / "tests"

    _write(
        test_dir / "test_checkout.py",
        '''
        def test_apply_discount(page):
            """Apply a valid discount.

            @spec: LIN-123
            """
            assert True


        # @spec: LIN-124
        def test_invalid_code(page):
            assert True


        def test_unrelated():
            """No spec tag here."""
            pass
        ''',
    )

    from mk_spec_master.tools.auto_link import auto_link_tests_tool

    result = auto_link_tests_tool({"test_dir": str(test_dir)})

    assert result["files_scanned"] == 1
    assert result["tags_found"] == 2
    assert result["links_added"] == 2

    spec_ids = {d["spec_id"] for d in result["discoveries"]}
    assert spec_ids == {"LIN-123", "LIN-124"}

    node_ids = {d["test_node_id"] for d in result["discoveries"]}
    assert "test_checkout.py::test_apply_discount" in node_ids
    assert "test_checkout.py::test_invalid_code" in node_ids


def test_auto_link_dry_run_skips_writes(tmp_path, monkeypatch):
    _set_tmp_index(tmp_path, monkeypatch)
    test_dir = tmp_path / "tests"
    _write(
        test_dir / "test_x.py",
        '''
        def test_one():
            """@spec: SPEC-001"""
            pass
        ''',
    )

    from mk_spec_master.tools.auto_link import auto_link_tests_tool
    from mk_spec_master.index import load_index

    result = auto_link_tests_tool({"test_dir": str(test_dir), "dry_run": True})

    assert result["tags_found"] == 1
    assert result["links_added"] == 0
    assert result["links_updated"] == 0
    assert result["dry_run"] is True

    # Index should be empty — dry run touched nothing.
    assert load_index().get("specs") in ({}, None)


def test_auto_link_writes_to_index(tmp_path, monkeypatch):
    _set_tmp_index(tmp_path, monkeypatch)
    test_dir = tmp_path / "tests"
    _write(
        test_dir / "test_y.py",
        '''
        def test_two():
            """@spec: SPEC-002"""
            pass
        ''',
    )

    from mk_spec_master.tools.auto_link import auto_link_tests_tool
    from mk_spec_master.index import load_index

    result = auto_link_tests_tool({"test_dir": str(test_dir)})
    assert result["links_added"] == 1

    index = load_index()
    assert "SPEC-002" in index.get("specs", {})
    linked = index["specs"]["SPEC-002"]["linked_tests"]
    assert any(t["node_id"] == "test_y.py::test_two" for t in linked)


def test_auto_link_re_run_updates_not_duplicates(tmp_path, monkeypatch):
    _set_tmp_index(tmp_path, monkeypatch)
    test_dir = tmp_path / "tests"
    _write(
        test_dir / "test_z.py",
        '''
        def test_three():
            """@spec: SPEC-003"""
            pass
        ''',
    )

    from mk_spec_master.tools.auto_link import auto_link_tests_tool

    first = auto_link_tests_tool({"test_dir": str(test_dir)})
    assert first["links_added"] == 1

    second = auto_link_tests_tool({"test_dir": str(test_dir)})
    # Same tag, same test — re-running upgrades to "updated".
    assert second["links_added"] == 0
    assert second["links_updated"] == 1


# ---------- JS / TS --------------------------------------------------


def test_auto_link_finds_js_test_block_tags(tmp_path, monkeypatch):
    _set_tmp_index(tmp_path, monkeypatch)
    test_dir = tmp_path / "tests"
    _write(
        test_dir / "checkout.spec.ts",
        '''
        // @spec: LIN-555
        it('applies discount', () => {
            // body
        });

        test('rejects invalid code', () => {
            /**
             * @spec LIN-556
             */
        });
        ''',
    )

    from mk_spec_master.tools.auto_link import auto_link_tests_tool

    result = auto_link_tests_tool({"test_dir": str(test_dir), "languages": ["js"]})
    assert result["tags_found"] == 2
    names = {d["test_node_id"].split("::")[-1] for d in result["discoveries"]}
    assert "applies discount" in names
    assert "rejects invalid code" in names


# ---------- Go -------------------------------------------------------


def test_auto_link_finds_go_test_tags(tmp_path, monkeypatch):
    _set_tmp_index(tmp_path, monkeypatch)
    test_dir = tmp_path / "tests"
    _write(
        test_dir / "checkout_test.go",
        '''
        package checkout

        import "testing"

        // @spec: GO-1
        func TestApplyDiscount(t *testing.T) {
            // body
        }
        ''',
    )

    from mk_spec_master.tools.auto_link import auto_link_tests_tool

    result = auto_link_tests_tool({"test_dir": str(test_dir), "languages": ["go"]})
    assert result["tags_found"] == 1
    assert result["discoveries"][0]["test_node_id"].endswith("::TestApplyDiscount")
    assert result["discoveries"][0]["spec_id"] == "GO-1"


# ---------- edge cases -----------------------------------------------


def test_auto_link_missing_dir_returns_error(tmp_path):
    from mk_spec_master.tools.auto_link import auto_link_tests_tool

    result = auto_link_tests_tool({"test_dir": str(tmp_path / "nonexistent")})
    assert "error" in result


def test_auto_link_skips_tag_without_surrounding_test(tmp_path, monkeypatch):
    """A `@spec:` floating in a non-test context shouldn't link to
    nothing — better to skip than to emit garbage node ids."""
    _set_tmp_index(tmp_path, monkeypatch)
    test_dir = tmp_path / "tests"
    _write(
        test_dir / "helpers.py",
        '''
        # @spec: LIN-999
        # (this isn't inside any test function)

        CONST = 1
        ''',
    )

    from mk_spec_master.tools.auto_link import auto_link_tests_tool

    result = auto_link_tests_tool({"test_dir": str(test_dir)})
    assert result["tags_found"] == 0


def test_auto_link_default_test_dir_falls_back_to_project_root(tmp_path, monkeypatch):
    """If SPEC_PROJECT_ROOT/tests doesn't exist, scan SPEC_PROJECT_ROOT
    itself rather than erroring out."""
    from mk_spec_master import config

    _set_tmp_index(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)

    _write(
        tmp_path / "stray_tests.py",
        '''
        def test_stray():
            """@spec: STRAY-1"""
            pass
        ''',
    )

    from mk_spec_master.tools.auto_link import auto_link_tests_tool

    result = auto_link_tests_tool({})
    assert result["test_dir"] == str(tmp_path)
    assert result["tags_found"] == 1


def test_auto_link_markdown_contains_summary(tmp_path, monkeypatch):
    _set_tmp_index(tmp_path, monkeypatch)
    test_dir = tmp_path / "tests"
    _write(
        test_dir / "test_a.py",
        '''
        def test_a():
            """@spec: A-1"""
            pass
        ''',
    )

    from mk_spec_master.tools.auto_link import auto_link_tests_tool

    md = auto_link_tests_tool({"test_dir": str(test_dir)})["markdown"]
    assert "Auto-link report" in md
    assert "Files scanned" in md
    assert "Links added" in md
