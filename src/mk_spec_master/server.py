"""MCP entrypoint. Registers + dispatches the v0.2 tool surface.

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
from .tools import quality as quality_tools
from .tools import auto_link as auto_link_tools
from .tools import optimization as optimization_tools
from .tools import spec_knowledge as spec_knowledge_tools

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
    "get_coverage_matrix": coverage_tools.get_coverage_matrix_tool,
    "get_drift_report": coverage_tools.get_drift_report_tool,
    "analyze_spec_quality": quality_tools.analyze_spec_quality_tool,
    "propose_spec_improvements": quality_tools.propose_spec_improvements_tool,
    "auto_link_tests": auto_link_tools.auto_link_tests_tool,
    "get_optimization_plan": optimization_tools.get_optimization_plan_tool,
    "init_spec_knowledge": spec_knowledge_tools.init_spec_knowledge_tool,
    "get_spec_context": spec_knowledge_tools.get_spec_context_tool,
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
                "matrix stays current. Pass `spec_title` / `spec_source` / "
                "`spec_url` (typically already known from earlier fetch_spec) "
                "to cache them into the index so get_coverage_matrix can "
                "render titles without re-fetching from the source. Pass "
                "`ac_hash` (from parse_spec._meta.ac_hash) to enable drift "
                "detection via get_drift_report. "
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
                    "spec_title": {"type": "string"},
                    "spec_source": {"type": "string"},
                    "spec_url": {"type": "string"},
                    "ac_hash": {
                        "type": "string",
                        "description": "SHA-256 of the canonical AC block, as returned by parse_spec._meta.ac_hash. Enables drift detection.",
                    },
                },
                "required": ["spec_id", "test_node_id"],
            },
        ),
        Tool(
            name="get_coverage_matrix",
            description=(
                "Snapshot of every spec ↔ test link recorded in the local "
                "index. Returns both structured rows and a ready-to-paste "
                "markdown table — call this when a user asks 'what's tested' "
                "or 'which specs have no tests'. "
                "Filters: `min_tests` (default 0; set to 0 to find untested "
                "specs, set to 1 to hide them) and `include_orphans` (default "
                "true). "
                "Returns {specs_total, specs_shown, specs_untested, "
                "orphan_count, rows[], markdown}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "min_tests": {"type": "integer", "default": 0},
                    "include_orphans": {"type": "boolean", "default": True},
                },
            },
        ),
        Tool(
            name="get_drift_report",
            description=(
                "For every spec in the index that has a stored ac_hash, "
                "fetch the live spec via the active adapter and recompute "
                "its ac_hash to detect drift. Buckets the results into "
                "fresh (no drift), drifted (linked tests may be stale), "
                "unknown (no hash stored — re-link with ac_hash from "
                "parse_spec._meta.ac_hash to enable), and stranded "
                "(spec_id can no longer be fetched — deleted, closed, or "
                "source mismatch). "
                "Use when a user asks 'has anything changed' / 'what's "
                "out of sync' / 'is my test suite still aligned with "
                "specs'. Optional `spec_id` narrows the check to one spec. "
                "Returns counts + per-bucket details + markdown summary."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "spec_id": {"type": "string"},
                },
            },
        ),
        Tool(
            name="analyze_spec_quality",
            description=(
                "Run heuristic checks against a spec's body: vague language "
                "without measurable thresholds (fast / easy / intuitive / "
                "現代 / 順暢 ...), implementation-detail leakage in AC ('uses "
                "Redis', '透過 X 服務'), and references to roles ('logged-in "
                "user', '管理員') without a Preconditions section. Pass "
                "`spec_id` for one spec, `raw_text` to analyze a freeform "
                "draft, or neither to sweep every spec from the active "
                "source. "
                "Returns {source, specs_analyzed, total_findings, results[]}. "
                "Each result has {spec_id, title, ac_count, score (0–100), "
                "findings[]} where each finding carries severity (info / "
                "warn / error), evidence, and a suggested rewrite. Pair with "
                "propose_spec_improvements for the markdown coach plan."
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
            name="propose_spec_improvements",
            description=(
                "Take analyze_spec_quality output and produce a PM-facing "
                "markdown coach plan grouping findings by spec and issue type, "
                "with concrete rewrite suggestions per finding. If `analysis` "
                "is not provided, runs analyze_spec_quality inline with the "
                "remaining arguments. Use this when a user says 'how do I "
                "improve this spec' or 'review my PRD'. "
                "Returns {markdown, actions[]}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "analysis": {
                        "type": "object",
                        "description": "Output of analyze_spec_quality. If omitted, this tool runs the analysis itself.",
                    },
                    "spec_id": {"type": "string"},
                    "raw_text": {"type": "string"},
                },
            },
        ),
        Tool(
            name="auto_link_tests",
            description=(
                "Scan a directory of test files for `@spec: <ID>` tags in "
                "docstrings or comments and call link_test_to_spec for each "
                "(test, spec) pair found. Supports Python (`def test_*`), "
                "JS/TS (`it('...')` / `test('...')`), and Go (`func "
                "TestX(t *testing.T)`). For each tag the nearest preceding "
                "test function within 30 lines is treated as the owner; "
                "test_node_id is `<relative-path>::<test-name>`. "
                "Use when a user says 'rebuild the spec coverage' or "
                "'sync test → spec links after the refactor'. Set "
                "`dry_run: true` to preview without writing. "
                "Returns {test_dir, files_scanned, tags_found, "
                "links_added, links_updated, skipped, discoveries[], "
                "markdown, dry_run}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "test_dir": {
                        "type": "string",
                        "description": "Absolute path to scan. Defaults to SPEC_PROJECT_ROOT/tests, falling back to SPEC_PROJECT_ROOT.",
                    },
                    "languages": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["python", "js", "go"]},
                        "description": "Subset of supported languages. Default: all three.",
                    },
                    "dry_run": {"type": "boolean", "default": False},
                },
            },
        ),
        Tool(
            name="get_optimization_plan",
            description=(
                "Three-layer coach output that integrates coverage / "
                "quality / drift signals into one prioritized markdown "
                "plan. Layer 1 surfaces untested + thin-coverage specs; "
                "Layer 2 ranks specs by severity-weighted quality findings; "
                "Layer 3 surfaces drifted + stranded specs. Use this when "
                "a user asks 'what should we fix next' / 'show me the "
                "weekly plan' / 'review the suite'. "
                "Toggle layers via include_coverage / include_quality / "
                "include_drift booleans (all default true). top_n caps "
                "per-layer detail rows (default 10). "
                "Returns {specs_total, *_count, *[], markdown}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "include_coverage": {"type": "boolean", "default": True},
                    "include_quality": {"type": "boolean", "default": True},
                    "include_drift": {"type": "boolean", "default": True},
                    "top_n": {"type": "integer", "default": 10},
                },
            },
        ),
        Tool(
            name="init_spec_knowledge",
            description=(
                "Create SPEC_PROJECT_ROOT/spec-knowledge.md from a starter "
                "template. The file carries spec methodology (EARS, INVEST, "
                "AC quality rules) plus TODO sections for the team's domain "
                "rules / actors / glossary. Other mk-spec-master tools "
                "lean on this indirectly via get_spec_context. Idempotent "
                "— refuses to overwrite an existing file unless "
                "overwrite=true. Optional project_name labels the file."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "overwrite": {"type": "boolean", "default": False},
                },
            },
        ),
        Tool(
            name="get_spec_context",
            description=(
                "Read SPEC_PROJECT_ROOT/spec-knowledge.md (or fall back to "
                "built-in defaults if missing). Call near the start of a "
                "session so the same methodology + domain glossary colours "
                "every spec interpretation that follows. Optional "
                "`section` filters to a single heading (partial-match, "
                "case-insensitive) — e.g. section='actors' returns just "
                "the actors block. "
                "Returns {source: 'file'|'builtin', content, ...}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "description": "Optional heading filter (partial match, case-insensitive).",
                    },
                },
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
