"""Linear adapter tests — monkeypatch _gql to avoid live API calls.

Real-API smoke tests are deliberately out of scope here; they'd require
a Linear workspace + valid API key in CI and would couple the test
suite to a third-party service. The split:

- Logic (filter construction, response parsing, error mapping) → unit
  tested here against a fake _gql.
- Wire-level (auth headers, URL, JSON shape) → relied on Linear's
  stable public GraphQL contract. If they break it we'll find out via
  user reports, not CI noise.
"""

from typing import Any

import pytest


# ---------- helpers --------------------------------------------------


def _fake_gql_returning(responses: dict[str, Any]):
    """Returns a stub _gql(query, variables=None) function that picks a
    response by the first identifier in the query (Issues / Issue)."""

    def _fake(query: str, variables=None):
        if "issueByIdentifier" in query:
            return responses["fetch"]
        if "issues(" in query:
            return responses["list"]
        return {}

    return _fake


def _node(identifier: str, title: str, state: str = "In Progress", labels=None):
    return {
        "id": f"uuid-{identifier}",
        "identifier": identifier,
        "title": title,
        "state": {"name": state},
        "labels": {"nodes": [{"name": l} for l in (labels or [])]},
        "url": f"https://linear.app/team/issue/{identifier}",
    }


# ---------- adapter logic ---------------------------------------------


def test_linear_list_specs_parses_nodes(monkeypatch):
    from mk_spec_master.adapters import linear

    monkeypatch.setattr(
        linear,
        "_gql",
        _fake_gql_returning(
            {
                "list": {
                    "issues": {
                        "nodes": [
                            _node("ENG-1", "Add discount code", labels=["checkout"]),
                            _node("ENG-2", "Fix CSS", state="Done"),
                        ]
                    }
                }
            }
        ),
    )

    adapter = linear.LinearAdapter()
    result = adapter.list_specs()

    assert len(result) == 2
    ids = [r.id for r in result]
    assert ids == ["ENG-1", "ENG-2"]
    assert result[0].labels == ["checkout"]
    assert result[1].status == "Done"


def test_linear_list_specs_respects_limit(monkeypatch):
    from mk_spec_master.adapters import linear

    monkeypatch.setattr(
        linear,
        "_gql",
        _fake_gql_returning(
            {"list": {"issues": {"nodes": [_node(f"ENG-{i}", f"Title {i}") for i in range(10)]}}}
        ),
    )

    adapter = linear.LinearAdapter()
    result = adapter.list_specs(limit=3)
    assert len(result) == 3


def test_linear_fetch_returns_spec_with_body(monkeypatch):
    from mk_spec_master.adapters import linear

    issue = _node("ENG-42", "Login feature")
    issue["description"] = "## Acceptance criteria\n1. The user can log in"
    issue["createdAt"] = "2026-01-01T00:00:00Z"
    issue["updatedAt"] = "2026-01-02T00:00:00Z"

    monkeypatch.setattr(
        linear,
        "_gql",
        _fake_gql_returning({"fetch": {"issueByIdentifier": issue}}),
    )

    adapter = linear.LinearAdapter()
    spec = adapter.fetch("ENG-42")

    assert spec.id == "ENG-42"
    assert spec.title == "Login feature"
    assert "log in" in spec.body
    assert spec.metadata["linear_id"] == "uuid-ENG-42"
    assert spec.metadata["created_at"] == "2026-01-01T00:00:00Z"


def test_linear_fetch_missing_issue_raises(monkeypatch):
    from mk_spec_master.adapters import linear

    monkeypatch.setattr(
        linear,
        "_gql",
        _fake_gql_returning({"fetch": {"issueByIdentifier": None}}),
    )

    adapter = linear.LinearAdapter()
    with pytest.raises(ValueError, match="not found"):
        adapter.fetch("ENG-9999")


def test_linear_check_auth_raises_without_api_key(monkeypatch):
    from mk_spec_master.adapters import linear
    from mk_spec_master import config

    monkeypatch.setattr(config, "LINEAR_API_KEY", "")

    with pytest.raises(linear.LinearUnavailable, match="LINEAR_API_KEY"):
        linear._check_auth()


def test_linear_check_auth_passes_with_api_key(monkeypatch):
    from mk_spec_master.adapters import linear
    from mk_spec_master import config

    monkeypatch.setattr(config, "LINEAR_API_KEY", "lin_api_dummy")
    assert linear._check_auth() == "lin_api_dummy"


def test_linear_registered_in_adapter_registry():
    from mk_spec_master.adapters import REGISTRY, get_source

    assert "linear" in REGISTRY
    src = get_source("linear")
    assert src.name == "linear"
