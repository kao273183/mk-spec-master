"""Figma adapter tests — monkeypatch _request to avoid live API calls.

Wire-level concerns (auth header name, file URL shape) are left to
real-world smoke; this suite covers parsing + tree-walking logic.
"""

import pytest


# ---------- fixtures ------------------------------------------------


def _frame(node_id: str, name: str, children=None):
    return {
        "id": node_id,
        "name": name,
        "type": "FRAME",
        "children": children or [],
    }


def _text(text_id: str, characters: str):
    return {
        "id": text_id,
        "name": "Text",
        "type": "TEXT",
        "characters": characters,
        "children": [],
    }


def _comment(message: str, anchor_node_id: str, handle: str = "designer"):
    return {
        "id": "comment-" + message[:8],
        "message": message,
        "user": {"handle": handle},
        "client_meta": {"node_id": anchor_node_id},
    }


def _file_response(frames_per_page: list[list[dict]]):
    """Top-level shape of GET /v1/files/{key}."""
    return {
        "document": {
            "id": "doc",
            "name": "doc",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": f"canvas-{i}",
                    "name": f"Page {i}",
                    "type": "CANVAS",
                    "children": frames,
                }
                for i, frames in enumerate(frames_per_page)
            ],
        }
    }


# ---------- helpers ----------------------------------------------------


def test_extract_text_collects_text_nodes_depth_first():
    from mk_spec_master.adapters.figma import _extract_text

    frame = _frame(
        "f1",
        "Login screen",
        [
            _text("t1", "Login"),
            _frame(
                "g1",
                "Form",
                [
                    _text("t2", "Email"),
                    _text("t3", "Password"),
                ],
            ),
            _text("t4", "Sign in"),
        ],
    )
    result = _extract_text(frame)
    # Order: t1, then form (t2, t3), then t4.
    lines = result.split("\n")
    assert lines == ["Login", "Email", "Password", "Sign in"]


def test_collect_node_ids_walks_subtree():
    from mk_spec_master.adapters.figma import _collect_node_ids

    frame = _frame(
        "f1",
        "Frame",
        [
            _text("t1", "a"),
            _frame("g1", "Group", [_text("t2", "b")]),
        ],
    )
    ids: set[str] = set()
    _collect_node_ids(frame, ids)
    assert ids == {"f1", "t1", "g1", "t2"}


def test_comments_filter_matches_anchored_subtree_nodes():
    from mk_spec_master.adapters.figma import _comments_for_subtree

    comments = [
        _comment("Looks good", "t1"),
        _comment("Unrelated", "other-node"),
        _comment("On nested text", "t2"),
    ]
    result = _comments_for_subtree(comments, {"f1", "t1", "g1", "t2"})
    messages = [c["message"] for c in result]
    assert "Looks good" in messages
    assert "On nested text" in messages
    assert "Unrelated" not in messages


# ---------- adapter logic -------------------------------------------


def test_figma_list_specs_returns_top_level_frames(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import figma

    monkeypatch.setattr(config, "SOURCE_KEY", "FILE123")
    monkeypatch.setattr(
        figma,
        "_request",
        lambda path, params=None: _file_response(
            [
                [_frame("1:1", "Login"), _frame("1:2", "Signup")],
                [_frame("2:1", "Dashboard")],
            ]
        ),
    )

    adapter = figma.FigmaAdapter()
    result = adapter.list_specs()
    ids = [r.id for r in result]
    titles = [r.title for r in result]
    assert ids == ["1:1", "1:2", "2:1"]
    assert titles == ["Login", "Signup", "Dashboard"]
    # URL format should embed the file key + node id.
    assert "FILE123" in result[0].url
    assert "1%3A1" in result[0].url  # url-encoded ':'


def test_figma_list_specs_respects_limit(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import figma

    monkeypatch.setattr(config, "SOURCE_KEY", "FILE")
    monkeypatch.setattr(
        figma,
        "_request",
        lambda path, params=None: _file_response(
            [[_frame(f"f{i}", f"Frame {i}") for i in range(10)]]
        ),
    )

    adapter = figma.FigmaAdapter()
    assert len(adapter.list_specs(limit=3)) == 3


def test_figma_list_specs_skips_section_type(monkeypatch):
    """SECTION wrappers shouldn't be returned as specs themselves."""
    from mk_spec_master import config
    from mk_spec_master.adapters import figma

    monkeypatch.setattr(config, "SOURCE_KEY", "FILE")
    sections_and_frames = [
        {"id": "s1", "name": "Section", "type": "SECTION", "children": []},
        _frame("f1", "Real frame"),
    ]
    monkeypatch.setattr(
        figma,
        "_request",
        lambda path, params=None: _file_response([sections_and_frames]),
    )

    adapter = figma.FigmaAdapter()
    result = adapter.list_specs()
    assert [r.id for r in result] == ["f1"]


def test_figma_fetch_returns_spec_with_text_and_comments(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import figma

    monkeypatch.setattr(config, "SOURCE_KEY", "FILE")

    frame = _frame(
        "1:1",
        "Login screen",
        [
            _text("t1", "Acceptance criteria"),
            _text("t2", "1. The user can log in"),
            _text("t3", "2. The user can log out"),
        ],
    )

    def fake_request(path, params=None):
        if path == "/files/FILE/nodes":
            return {"nodes": {"1:1": {"document": frame}}}
        if path == "/files/FILE/comments":
            return {
                "comments": [
                    _comment("LGTM", "1:1"),
                    _comment("Unrelated comment", "elsewhere"),
                ]
            }
        return {}

    monkeypatch.setattr(figma, "_request", fake_request)

    adapter = figma.FigmaAdapter()
    spec = adapter.fetch("1:1")
    assert spec.id == "1:1"
    assert spec.title == "Login screen"
    assert "Acceptance criteria" in spec.body
    assert "1. The user can log in" in spec.body
    assert "## Comments" in spec.body
    assert "LGTM" in spec.body
    assert "Unrelated comment" not in spec.body


def test_figma_fetch_missing_node_raises(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import figma

    monkeypatch.setattr(config, "SOURCE_KEY", "FILE")
    monkeypatch.setattr(figma, "_request", lambda path, params=None: {"nodes": {}})

    adapter = figma.FigmaAdapter()
    with pytest.raises(ValueError, match="not found"):
        adapter.fetch("99:99")


# ---------- auth checks ---------------------------------------------


def test_figma_check_auth_raises_without_token(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import figma

    monkeypatch.setattr(config, "FIGMA_TOKEN", "")
    with pytest.raises(figma.FigmaUnavailable, match="FIGMA_TOKEN"):
        figma._check_auth()


def test_figma_file_key_required(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import figma

    monkeypatch.setattr(config, "SOURCE_KEY", "")
    with pytest.raises(figma.FigmaUnavailable, match="SPEC_PROJECT_KEY"):
        figma._file_key()


def test_figma_registered_in_adapter_registry():
    from mk_spec_master.adapters import REGISTRY, get_source

    assert "figma" in REGISTRY
    src = get_source("figma")
    assert src.name == "figma"
