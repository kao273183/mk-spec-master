"""JIRA adapter tests — same approach as test_linear: monkeypatch the
HTTP boundary so live API calls aren't required."""

import pytest


# ---------- fixtures -------------------------------------------------


def _issue(key: str, summary: str, status: str = "In Progress", labels=None, description=None):
    return {
        "id": f"id-{key}",
        "key": key,
        "self": f"https://yourorg.atlassian.net/rest/api/3/issue/{key}",
        "fields": {
            "summary": summary,
            "status": {"name": status},
            "labels": labels or [],
            "description": description,
            "issuetype": {"name": "Story"},
            "created": "2026-01-01T00:00:00.000+0000",
            "updated": "2026-01-02T00:00:00.000+0000",
        },
    }


# ---------- ADF → markdown ------------------------------------------


def test_adf_to_markdown_handles_heading_and_list():
    from mk_spec_master.adapters.jira import adf_to_markdown

    adf = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Acceptance criteria"}],
            },
            {
                "type": "orderedList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "User can log in"}]},
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "User can log out"}]},
                        ],
                    },
                ],
            },
        ],
    }

    md = adf_to_markdown(adf)
    assert "## Acceptance criteria" in md
    assert "1. " in md and "User can log in" in md
    assert "2. " in md and "User can log out" in md


def test_adf_to_markdown_handles_plain_string_and_none():
    """JIRA Server sometimes returns description as a plain string; v3
    Cloud may return None for unset descriptions. Both must be safe."""
    from mk_spec_master.adapters.jira import adf_to_markdown

    assert adf_to_markdown(None) == ""
    assert adf_to_markdown("just text") == "just text"


# ---------- JQL builder ---------------------------------------------


def test_build_jql_combines_filters():
    from mk_spec_master.adapters.jira import _build_jql

    jql = _build_jql("PROJ", status="In Progress", label="critical")
    assert "project = \"PROJ\"" in jql
    assert "status = \"In Progress\"" in jql
    assert "labels = \"critical\"" in jql
    assert "ORDER BY updated DESC" in jql


def test_build_jql_no_filters_returns_order_only():
    from mk_spec_master.adapters.jira import _build_jql

    jql = _build_jql("", status=None, label=None)
    assert jql == "ORDER BY updated DESC"


def test_build_jql_escapes_quotes_in_value():
    from mk_spec_master.adapters.jira import _build_jql

    jql = _build_jql("PROJ", status='in "review"', label=None)
    # Should escape inner quotes so JQL parses.
    assert '\\"review\\"' in jql


# ---------- adapter logic -------------------------------------------


def test_jira_list_specs_parses_issues(monkeypatch):
    from mk_spec_master.adapters import jira

    monkeypatch.setattr(
        jira,
        "_request",
        lambda path, params=None: {
            "issues": [
                _issue("PROJ-1", "Add discount code", labels=["checkout"]),
                _issue("PROJ-2", "Fix CSS", status="Done"),
            ]
        },
    )

    adapter = jira.JiraAdapter()
    result = adapter.list_specs()
    assert [r.id for r in result] == ["PROJ-1", "PROJ-2"]
    assert result[0].labels == ["checkout"]
    assert result[1].status == "Done"


def test_jira_list_specs_respects_limit(monkeypatch):
    from mk_spec_master.adapters import jira

    monkeypatch.setattr(
        jira,
        "_request",
        lambda path, params=None: {
            "issues": [_issue(f"PROJ-{i}", f"Item {i}") for i in range(10)]
        },
    )

    adapter = jira.JiraAdapter()
    result = adapter.list_specs(limit=3)
    assert len(result) == 3


def test_jira_fetch_returns_spec_with_body(monkeypatch):
    from mk_spec_master.adapters import jira

    adf = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Acceptance criteria"}],
            },
            {
                "type": "orderedList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "User can log in"}]}],
                    }
                ],
            },
        ],
    }

    monkeypatch.setattr(
        jira,
        "_request",
        lambda path, params=None: _issue("PROJ-42", "Login feature", description=adf),
    )

    adapter = jira.JiraAdapter()
    spec = adapter.fetch("PROJ-42")
    assert spec.id == "PROJ-42"
    assert "Acceptance criteria" in spec.body
    assert "log in" in spec.body
    assert spec.metadata["jira_id"] == "id-PROJ-42"


def test_jira_fetch_missing_issue_raises(monkeypatch):
    from mk_spec_master.adapters import jira

    monkeypatch.setattr(jira, "_request", lambda path, params=None: {})

    adapter = jira.JiraAdapter()
    with pytest.raises(ValueError, match="not found"):
        adapter.fetch("PROJ-99999")


# ---------- auth checks --------------------------------------------


def test_jira_check_auth_missing_base_url(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import jira

    monkeypatch.setattr(config, "JIRA_BASE_URL", "")
    monkeypatch.setattr(config, "JIRA_EMAIL", "you@example.com")
    monkeypatch.setattr(config, "JIRA_API_TOKEN", "tok")

    with pytest.raises(jira.JiraUnavailable, match="JIRA_BASE_URL"):
        jira._check_auth()


def test_jira_check_auth_missing_email(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import jira

    monkeypatch.setattr(config, "JIRA_BASE_URL", "https://x.atlassian.net")
    monkeypatch.setattr(config, "JIRA_EMAIL", "")
    monkeypatch.setattr(config, "JIRA_API_TOKEN", "tok")

    with pytest.raises(jira.JiraUnavailable, match="JIRA_EMAIL"):
        jira._check_auth()


def test_jira_check_auth_missing_token(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import jira

    monkeypatch.setattr(config, "JIRA_BASE_URL", "https://x.atlassian.net")
    monkeypatch.setattr(config, "JIRA_EMAIL", "you@example.com")
    monkeypatch.setattr(config, "JIRA_API_TOKEN", "")

    with pytest.raises(jira.JiraUnavailable, match="JIRA_API_TOKEN"):
        jira._check_auth()


def test_jira_check_auth_all_set_passes(monkeypatch):
    from mk_spec_master import config
    from mk_spec_master.adapters import jira

    monkeypatch.setattr(config, "JIRA_BASE_URL", "https://x.atlassian.net")
    monkeypatch.setattr(config, "JIRA_EMAIL", "you@example.com")
    monkeypatch.setattr(config, "JIRA_API_TOKEN", "tok")
    base, email, tok = jira._check_auth()
    assert base == "https://x.atlassian.net"


def test_jira_registered_in_adapter_registry():
    from mk_spec_master.adapters import REGISTRY, get_source

    assert "jira" in REGISTRY
    src = get_source("jira")
    assert src.name == "jira"
