"""MCP entrypoint. Registers + dispatches the v0.1 tool surface.

Tool descriptions are written to read like operating manuals — they tell
the AI client when to call this vs another tool, what shape comes back,
and which downstream tool (often mk-qa-master) to hand off to.
"""

import asyncio
import json
from typing import Any, Callable

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from . import __version__
from .adapters import REGISTRY
from .config import SOURCE_NAME
from .tools import specs as specs_tools
from .tools import scenarios as scenarios_tools
from .tools import coverage as coverage_tools

app = Server("mk-spec-master")


def _meta_info(_: dict) -> dict[str, Any]:
    return {
        "active": SOURCE_NAME,
        "available": sorted(REGISTRY),
        "version": __version__,
    }


_DISPATCH: dict[str, Callable[[dict], dict]] = {
    "get_spec_source_info": _meta_info,
    "list_specs": specs_tools.list_specs_tool,
    "fetch_spec": specs_tools.fetch_spec_tool,
    "parse_spec": specs_tools.parse_spec_tool,
    "extract_scenarios": scenarios_tools.extract_scenarios_tool,
    "generate_test_plan": scenarios_tools.generate_test_plan_tool,
    "link_test_to_spec": coverage_tools.link_test_to_spec_tool,
}


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_spec_source_info",
            description=(
                "Return the active spec source (selected via SPEC_SOURCE env var) "
                "plus all adapters built into this server. Call first in any "
                "session so the AI knows whether to expect markdown / GitHub / "
                "(future) Linear / JIRA / Notion semantics. "
                "Returns {active, available, version}."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_specs",
            description=(
                "Enumerate specs from the active source. For markdown_local this "
                "globs SPEC_PROJECT_ROOT/specs/*.md and reads YAML frontmatter; "
                "for github_issues it queries the configured owner/repo (set via "
                "SPEC_PROJECT_KEY). Optional filters: status (string — adapter-"
                "specific: 'in-progress' for markdown, 'open'|'closed'|'all' for "
                "GitHub), label (string), limit (int, default 50). "
                "Returns {source, count, specs[]}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "label": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        ),
        Tool(
            name="fetch_spec",
            description=(
                "Pull a single spec by id from the active source. For markdown_local "
                "the id is either the `id:` field in frontmatter or the filename "
                "stem; for github_issues it's the issue number as string. Returns "
                "the full Spec record {id, title, body, url, status, labels, metadata}. "
                "Pair with parse_spec to extract structured acceptance criteria."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "spec_id": {"type": "string"},
                },
                "required": ["spec_id"],
            },
        ),
        Tool(
            name="parse_spec",
            description=(
                "Extract structured acceptance criteria from a spec body. Looks for "
                "headings matching 'Acceptance criteria' / 'AC' / '驗收條件' / "
                "'驗收標準' (case-insensitive, en + zh-TW + zh-CN) and pulls "
                "numbered or bulleted items beneath. Pass `spec_id` to use the "
                "active adapter, or `raw_text` to parse ad-hoc spec text without "
                "going through any source. "
                "Returns {spec_id, title, acceptance_criteria[], roles[], "
                "preconditions[], _meta}. Roles + preconditions are placeholders "
                "in v0.1 — filled by the v0.2 spec-quality coach."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "spec_id": {"type": "string"},
                    "raw_text": {"type": "string"},
                },
            },
        ),
        Tool(
            name="extract_scenarios",
            description=(
                "Turn parsed acceptance criteria into testable scenarios. Each "
                "scenario is classified as happy / edge / error via keyword "
                "heuristics, and split into Given / When / Then where possible. "
                "Pass the `acceptance_criteria` array returned by parse_spec. "
                "Returns {count, scenarios[]} where each scenario has "
                "{id, ac_id, title, kind, given, when, then}. Best paired with "
                "generate_test_plan for a markdown handoff to mk-qa-master."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "acceptance_criteria": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "text": {"type": "string"},
                            },
                            "required": ["text"],
                        },
                    }
                },
                "required": ["acceptance_criteria"],
            },
        ),
        Tool(
            name="generate_test_plan",
            description=(
                "One-shot: fetch + parse + extract for a spec, then emit a markdown "
                "test plan with a `business_context` block per scenario ready to "
                "hand to `mk-qa-master.generate_test(business_context=...)`. The "
                "AI client typically reads this plan, loops the scenarios, and "
                "calls mk-qa-master once per scenario. Set `target_runner` to hint "
                "the desired output (pytest / jest / cypress / go / maestro). "
                "Returns {spec_id, target_runner, scenario_count, markdown, scenarios[]}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "spec_id": {"type": "string"},
                    "target_runner": {"type": "string", "default": "pytest"},
                },
                "required": ["spec_id"],
            },
        ),
        Tool(
            name="link_test_to_spec",
            description=(
                "Record that a test verifies a spec. Writes into "
                "SPEC_PROJECT_ROOT/.mk-spec-master/index.json (data ownership "
                "stays with the user). Re-linking the same node_id updates the "
                "timestamp instead of duplicating. Call this right after "
                "mk-qa-master.generate_test returns a node_id so the coverage "
                "matrix stays current. "
                "Returns {action: 'added'|'updated', spec_id, test_node_id, "
                "total_links_for_spec}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "spec_id": {"type": "string"},
                    "test_node_id": {
                        "type": "string",
                        "description": "Test framework node id, e.g. tests/test_checkout.py::test_apply_discount",
                    },
                },
                "required": ["spec_id", "test_node_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handler = _DISPATCH.get(name)
    if handler is None:
        return [_text({"error": f"unknown tool: {name}", "available": sorted(_DISPATCH)})]

    try:
        result = handler(arguments or {})
    except Exception as exc:
        # Surface a structured error rather than letting the MCP transport
        # swallow the exception silently.
        result = {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "tool": name,
        }
    return [_text(result)]


def _text(payload: dict) -> TextContent:
    return TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))


async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
