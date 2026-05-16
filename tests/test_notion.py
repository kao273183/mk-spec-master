"""Notion adapter tests — monkeypatch _request to avoid live API calls."""

import pytest


# ---------- block conversion ----------------------------------------


def test_blocks_to_markdown_handles_common_types():
    from mk_spec_master.adapters.notion import blocks_to_markdown

    blocks = [
        {
            "type": "heading_2",
            "heading_2": {"rich_text": [{"plain_text": "Acceptance criteria"}]},
        },
        {
            "type": "numbered_list_item",
            "numbered_list_item": {"rich_text": [{"plain_text": "User can log in"}]},
        },
        {
            "type": "numbered_list_item",
            "numbered_list_item": {"rich_text": [{"plain_text": "User can log out"}]},
        },
        {
            "type": "paragraph",
            "paragraph": {"rich_text": [{"plain_text": "Note: handle SSO later."}]},
        },
        {
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"plain_text": "Edge: locked account"}]},
        },
    ]

    md = blocks_to_markdown(blocks)
    assert "## Acceptance criteria" in md
    assert "1. User can log in" in md
    assert "2. User can log out" in md
    assert "Note: handle SSO later." in md
    assert "- Edge: locked account" in md


def test_blocks_to_markdown_resets_numbering_after_break():
    """Notion's numbered_list_item is per-block, not per-list. Restarting
    numbering at each streak boundary keeps the markdown legible when
    the database mixes paragraphs and numbered lists."""
    from mk_spec_master.adapters.notion import blocks_to_markdown

    blocks = [
        {"type": "numbered_list_item", "numbered_list_item": {"rich_text": [{"plain_text": "A"}]}},
        {"type": "numbered_list_item", "numbered_list_item": {"rich_text": [{"plain_text": "B"}]}},
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "—"}]}},
        {"type": "numbered_list_item", "numbered_list_item": {"rich_text": [{"plain_text": "C"}]}},
    ]
    md = blocks_to_markdown(blocks)
    assert "1. A" in md
    assert "2. B" in md
    # streak broke at the paragraph → restart at 1
    assert "1. C" in md


def test_blocks_to_markdown_handles_code_and_to_do():
    from mk_spec_master.adapters.notion import blocks_to_markdown

    blocks = [
        {"type": "code", "code": {"language": "python", "rich_text": [{"plain_text": "print('hi')"}]}},
        {"type": "to_do", "to_do": {"checked": True, "rich_text": [{"plain_text": "Done thing"}]}},
        {"type": "to_do", "to_do": {"checked": False, "rich_text": [{"plain_text": "Pending thing"}]}},
    ]
    md = blocks_to_markdown(blocks)
    assert "```python" in md
    assert "print('hi')" in md
    assert "[x] Done thing" in md
    assert "[ ] Pending thing" in md


# ---------- property extraction --------------------------------------


def _page(page_id="abc-123", title="Login feature", status="In Progress", labels=None, key=""):
    props = {
        "Name": {"type": "title", "title": [{"plain_text": title}]},
        "Status": {"type": "status", "status": {"name": status}},
    }
    if labels is not None:
        props["Tags"] = {
            "type": "multi_select",
            "multi_select": [{"name": l} for l in labels],
        }
    if key:
        props["Key"] = {"type": "rich_text", "rich_text": [{"plain_text": key}]}
    return {
        "object": "page",
        "id": page_id,
        "url": f"https://notion.so/{page_id}",
        "created_time": "2026-01-01T00:00:00.000Z",
        "last_edited_time": "2026-01-02T00:00:00.000Z",
        "properties": props,
    }


def test_extract_title_from_title_property():
    from mk_spec_master.adapters.notion import _extract_title

    assert _extract_title(_page(title="Apply discount")) == "Apply discount"


def test_extract_status_from_select_property():
    from mk_spec_master.adapters.notion import _extract_status

    # Page using `select` instead of `status` property type.
    page = _page()
    page["properties"]["Status"] = {"type": "select", "select": {"name": "Done"}}
    assert _extract_status(page) == "Done"


def test_extract_labels_from_multi_select():
    from mk_spec_master.adapters.notion import _extract_labels

    page = _page(labels=["checkout", "billing"])
    assert _extract_labels(page) == ["checkout", "billing"]


def test_extract_custom_key_from_rich_text_property():
    from mk_spec_master.adapters.notion import _extract_custom_key

    page = _page(key="SPEC-007")
    assert _extract_custom_key(page) == "SPEC-007"


# ---------- adapter logic --------------------------------------------


def test_notion_list_specs_parses_pages(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import notion

    monkeypatch.setattr(config, "SOURCE_KEY", "db-uuid-123")
    monkeypatch.setattr(
        notion,
        "_request",
        lambda method, path, body=None: {
            "results": [
                _page(page_id="page-1", title="Spec A", labels=["checkout"]),
                _page(page_id="page-2", title="Spec B", status="Done"),
            ]
        },
    )

    adapter = notion.NotionAdapter()
    result = adapter.list_specs()
    assert [r.id for r in result] == ["page-1", "page-2"]
    assert result[0].title == "Spec A"
    assert result[0].labels == ["checkout"]
    assert result[1].status == "Done"


def test_notion_list_specs_status_filter(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import notion

    monkeypatch.setattr(config, "SOURCE_KEY", "db-uuid")
    monkeypatch.setattr(
        notion,
        "_request",
        lambda method, path, body=None: {
            "results": [
                _page(page_id="p1", status="In Progress"),
                _page(page_id="p2", status="Done"),
                _page(page_id="p3", status="In Progress"),
            ]
        },
    )

    adapter = notion.NotionAdapter()
    result = adapter.list_specs(status="In Progress")
    assert [r.id for r in result] == ["p1", "p3"]


def test_notion_fetch_returns_spec_with_blocks_as_body(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import notion

    monkeypatch.setattr(config, "SOURCE_KEY", "db-uuid")

    page = _page(page_id="page-42", title="Login feature")
    children_response = {
        "results": [
            {"type": "heading_2", "heading_2": {"rich_text": [{"plain_text": "Acceptance criteria"}]}},
            {"type": "numbered_list_item", "numbered_list_item": {"rich_text": [{"plain_text": "User can log in"}]}},
            {"type": "numbered_list_item", "numbered_list_item": {"rich_text": [{"plain_text": "User can log out"}]}},
        ]
    }

    call_log = []

    def fake_request(method, path, body=None):
        call_log.append((method, path))
        if path.startswith("/pages/"):
            return page
        if path.startswith("/blocks/"):
            return children_response
        return {}

    monkeypatch.setattr(notion, "_request", fake_request)

    adapter = notion.NotionAdapter()
    spec = adapter.fetch("page-42")
    assert spec.id == "page-42"
    assert spec.title == "Login feature"
    assert "Acceptance criteria" in spec.body
    assert "log in" in spec.body
    assert call_log == [("GET", "/pages/page-42"), ("GET", "/blocks/page-42/children?page_size=100")]


def test_notion_fetch_missing_page_raises(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import notion

    monkeypatch.setattr(config, "SOURCE_KEY", "db-uuid")
    monkeypatch.setattr(notion, "_request", lambda method, path, body=None: {})

    adapter = notion.NotionAdapter()
    with pytest.raises(ValueError, match="not found"):
        adapter.fetch("page-does-not-exist")


# ---------- auth checks ----------------------------------------------


def test_notion_check_auth_raises_without_token(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import notion

    monkeypatch.setattr(config, "NOTION_TOKEN", "")
    with pytest.raises(notion.NotionUnavailable, match="NOTION_TOKEN"):
        notion._check_auth()


def test_notion_database_id_required_for_listing(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import notion

    monkeypatch.setattr(config, "SOURCE_KEY", "")
    with pytest.raises(notion.NotionUnavailable, match="SPEC_PROJECT_KEY"):
        notion._database_id()


def test_notion_registered_in_adapter_registry():
    from mk_spec_master.adapters import REGISTRY, get_source

    assert "notion" in REGISTRY
    src = get_source("notion")
    assert src.name == "notion"
