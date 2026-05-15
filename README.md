<p align="center">
  <img src="https://raw.githubusercontent.com/kao273183/mk-spec-master/main/assets/logo.png" alt="mk-spec-master logo" width="180" />
</p>

<h1 align="center">MK Spec Master</h1>

<p align="center">
  <em>AI 規格大師 — specs in, scenarios out. Bidirectional traceability so you always know what's tested.</em>
</p>

<p align="center">
  <strong>English</strong> · <a href="README.zh-TW.md">繁體中文</a>
</p>

<p align="center">
  <a href="https://pypi.org/project/mk-spec-master/"><img src="https://img.shields.io/pypi/v/mk-spec-master.svg?logo=pypi&logoColor=white&color=3775A9" alt="PyPI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/status-alpha-orange.svg" alt="Status: Alpha" />
</p>

> Spec-driven testing over MCP. Turn Linear / JIRA / GitHub Issues / Notion / Figma / Markdown specs into runnable scenarios, hand off to any test runner via [`mk-qa-master`](https://github.com/kao273183/mk-qa-master), and keep a live spec ↔ test coverage matrix.

> **🟢 Alpha — v0.2 partial.** 11 tools shipped (coverage matrix + spec-quality coach + drift report). Full design in [`docs/prd.md`](docs/prd.md). Next in v0.2: Linear / JIRA adapters.

---

## Install

```bash
uvx mk-spec-master    # or: pip install mk-spec-master
```

Add to your MCP client config:

```json
{
  "mcpServers": {
    "mk-spec-master": {
      "command": "uvx",
      "args": ["mk-spec-master"],
      "env": {
        "SPEC_SOURCE": "markdown_local",
        "SPEC_PROJECT_ROOT": "/path/to/your/project"
      }
    }
  }
}
```

Then in Claude / Cursor / Codex / Gemini CLI:

> "Use mk-spec-master to parse SPEC-001, extract scenarios, and hand them to mk-qa-master so we can generate Playwright tests."

## What this is

An MCP server that turns specs — Linear tickets, JIRA stories, GitHub Issues, Notion pages, Figma annotations, plain Markdown — into structured test scenarios, hands them to any test runner (via [`mk-qa-master`](https://github.com/kao273183/mk-qa-master) or directly), and maintains a live spec ↔ test coverage matrix.

Sibling to `mk-qa-master` in the `mk-*` family of opinionated AI-QA MCPs.

## Why this is missing from the ecosystem

| Tool | Lock-in | What we do differently |
|---|---|---|
| AWS Kiro | AWS IDE only, proprietary | MCP-native, multi-client, open source |
| Jama Connect MCP | $50k+/year, enterprise-only | SMB / indie / AI-native segment |
| GitHub Spec Kit | spec→code; runtime test coverage out of scope | We add runtime test coverage |
| testomat.io / JIRA MCPs | Single source (JIRA), SaaS lock | Multi-source, file-based index, no lock |

See [`docs/prd.md` §4](docs/prd.md) for the full positioning.

## Tool surface (v0.2 partial — 10 tools)

| Tool | Since | Purpose |
|---|---|---|
| `get_spec_source_info` | v0.1 | Active adapter + all available — call this first |
| `list_specs` | v0.1 | Enumerate specs from the active source (filter by status / label / limit) |
| `fetch_spec` | v0.1 | Pull a single spec's full content by id |
| `parse_spec` | v0.1 | Heuristic AC extraction (en + zh-TW + zh-CN headings supported); accepts `spec_id` or `raw_text` |
| `extract_scenarios` | v0.1 | AC → scenarios with happy / edge / error classification (negation-aware) and best-effort Given/When/Then split |
| `generate_test_plan` | v0.1 | One-shot fetch + parse + extract → markdown plan ready to feed to `mk-qa-master.generate_test(business_context=...)` |
| `link_test_to_spec` | v0.1 | Record that a test verifies a spec (writes to `SPEC_PROJECT_ROOT/.mk-spec-master/index.json`). v0.2: caches title / source / url for the matrix |
| `get_coverage_matrix` | **v0.2** | Spec × test grid — answer "which specs have no tests" in one call |
| `analyze_spec_quality` | **v0.2** | Heuristic coach — flags vague language, implementation-leak AC, unclear role refs (the differentiator vs Kiro / Spec Kit) |
| `propose_spec_improvements` | **v0.2** | Take analyze output → PM-facing markdown with concrete rewrites |
| `get_drift_report` | **v0.2.1** | For every spec with a stored ac_hash, fetch live + recompute + compare. Buckets results into fresh / drifted / unknown / stranded |

Still pending for full v0.2: Linear / JIRA adapters.

## Adapter status

| `SPEC_SOURCE` | Source | Status | Auth |
|---|---|---|---|
| `markdown_local` | Local `*.md` with YAML-ish frontmatter | ✅ since 0.1.0 | none |
| `github_issues` | GitHub Issues via `gh` CLI | ✅ since 0.1.0 | `gh auth login` or `GITHUB_TOKEN` |
| `linear` | Linear API | ⏳ pending — v0.2.x | `LINEAR_API_KEY` |
| `jira` | JIRA Cloud / Server | ⏳ pending — v0.2.x | `JIRA_API_TOKEN` + `JIRA_BASE_URL` |
| `notion` | Notion databases | ⏳ planned — v0.3 | `NOTION_TOKEN` |
| `figma` | Figma annotations + comments | ⏳ planned — v0.3 | `FIGMA_TOKEN` |

> v0.2.0 shipped the coverage matrix + spec-quality coach tools, not new adapters. Linear / JIRA adapters land in a follow-up 0.2.x release.

## Walkthrough — spec → test → coverage

Given a Linear ticket *LIN-123 "Apply discount at checkout"* with 4 acceptance criteria:

```
You: Use mk-spec-master to fetch LIN-123, extract scenarios, generate
     Playwright tests with mk-qa-master, run them, and report coverage.
```

The AI client chains:

```
mk-spec-master.fetch_spec("LIN-123")
mk-spec-master.parse_spec(spec_id="LIN-123")        → 4 AC
mk-spec-master.extract_scenarios(...)                → 1 happy + 3 error
mk-spec-master.generate_test_plan(spec_id="LIN-123")

for scenario in plan:
  mk-qa-master.generate_test(business_context=scenario.gherkin)
  mk-spec-master.link_test_to_spec(spec_id="LIN-123", test_node_id=...)

mk-qa-master.run_tests
```

The traceability index now records all 4 links. Next sprint, when the spec changes, `get_drift_report` (v0.2) will flag tests that may be stale.

## Status

| Milestone | Target | Status |
|---|---|---|
| v0.1 (MVP — markdown_local + github_issues, 7 tools) | June 2026 | ✅ Shipped |
| v0.2 (Linear, JIRA, coverage matrix, spec-quality coach, drift report) | Aug 2026 | 🟡 Coverage matrix + coach + drift report shipped (0.2.1); Linear / JIRA pending |
| v0.3 (Notion, Figma, auto-link, optimization plan) | Oct 2026 | ⬜ |
| v1.0 (production-ready, docs, integration recipes) | Q4 2026 | ⬜ |

## Family

- [`mk-qa-master`](https://github.com/kao273183/mk-qa-master) — AI 測試大師, the test-runner sibling. Tests run via mk-qa-master; coverage tracked here.
- More `mk-*` MCPs in design (`mk-perf-master`, `mk-a11y-master`).

## License

MIT — see [LICENSE](LICENSE).
