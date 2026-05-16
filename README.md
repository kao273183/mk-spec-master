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

> **🟢 Alpha — v0.4: self-reinforcement.** **18 tools** + 6 adapters. Snapshots archived per `get_optimization_plan` call → trend analysis + chronic-spec detection + tool-usage telemetry. Full design in [`docs/prd.md`](docs/prd.md).

---

## What this is

An MCP server that turns specs — Linear tickets, JIRA stories, GitHub Issues, Notion pages, Figma annotations, plain Markdown — into structured test scenarios, hands them to any test runner (via [`mk-qa-master`](https://github.com/kao273183/mk-qa-master) or directly), and maintains a live spec ↔ test coverage matrix.

Sibling to `mk-qa-master` in the `mk-*` family of opinionated AI-QA MCPs.

## What this is NOT

| It's not | Use this instead |
|---|---|
| A spec **editor** | Linear / JIRA / Notion / Markdown — keep writing specs where you already do |
| A **test runner** | [`mk-qa-master`](https://github.com/kao273183/mk-qa-master) (pytest / Jest / Cypress / Go test / Maestro) |
| An **issue tracker UI** | Linear / JIRA / Notion's native interface |
| A **spec → code** generator | GitHub Spec Kit, AWS Kiro |
| An **LLM** | Leverages your AI client (Claude / Cursor / Codex / Gemini) for the reasoning |

mk-spec-master sits **between** your spec source and your test runner — purely about the *spec ↔ test* link, the coverage matrix that lives on top, and the quality coach that grades both.

---

## Tool surface (15 tools)

Grouped by role. Each group is a layer in the spec→test→coverage→coach loop.

### Meta — orientation (1)

| Tool | Purpose |
|---|---|
| `get_spec_source_info` | Active adapter + all available. Call first so the AI knows whether to expect Linear / JIRA / Notion / Figma / Markdown semantics |

### Discovery — find and load specs (3)

| Tool | Purpose |
|---|---|
| `list_specs` | Enumerate specs from the active source (filter by status / label / limit) |
| `fetch_spec` | Pull a single spec's full content by id |
| `parse_spec` | Heuristic AC extraction (en + zh-TW + zh-CN headings supported); accepts `spec_id` or `raw_text`. Returns `_meta.ac_hash` for drift detection |

### Generation — specs → testable artifacts (2)

| Tool | Purpose |
|---|---|
| `extract_scenarios` | AC → scenarios with happy / edge / error classification (negation-aware) and best-effort Given/When/Then split |
| `generate_test_plan` | One-shot fetch + parse + extract → markdown plan ready to feed to `mk-qa-master.generate_test(business_context=...)` |

### Coverage & drift — the traceability layer (4)

| Tool | Purpose |
|---|---|
| `link_test_to_spec` | Record that a test verifies a spec (writes to `SPEC_PROJECT_ROOT/.mk-spec-master/index.json`). Stores title / source / url / ac_hash for the matrix and drift report |
| `auto_link_tests` | Scan a test directory for `@spec: <ID>` tags and link them automatically. Python / JS / TS / Go supported. `dry_run` previews without writing |
| `get_coverage_matrix` | Spec × test grid — answer "which specs have no tests" in one call |
| `get_drift_report` | Re-fetch each linked spec, recompute ac_hash, compare. Buckets into fresh / drifted / unknown / stranded |

### Coach — quality + prioritization (3)

| Tool | Purpose |
|---|---|
| `analyze_spec_quality` | Heuristic findings on vague language, implementation-leak AC, unclear role refs (the differentiator vs Kiro / Spec Kit) |
| `propose_spec_improvements` | Take analyze output → PM-facing markdown with concrete rewrites |
| `get_optimization_plan` | Three-layer prioritized plan: coverage gaps (L1) + spec-quality (L2) + process drift (L3). The "what should we fix next" tool |

### Knowledge — domain methodology (2)

| Tool | Purpose |
|---|---|
| `init_spec_knowledge` | Create `SPEC_PROJECT_ROOT/spec-knowledge.md` from a starter template (EARS, INVEST, AC quality rules + TODO sections for your team's rules / actors / glossary). Idempotent |
| `get_spec_context` | Read the spec-knowledge file (with built-in fallback). Optional `section` filter pulls one heading at a time. Call near the start of every session |

### Self-reinforcement — long-running view (3, v0.4)

| Tool | Purpose |
|---|---|
| `get_spec_history` | Last N snapshots archived by `get_optimization_plan`, with trend deltas (current vs ~7d, vs ~30d) for spec / coverage / quality / drift counters. "Are we improving?" |
| `get_drift_signature` | Scan recent snapshots for specs that repeatedly land in drifted / unknown / low-quality buckets — chronic patterns. "Which specs keep causing trouble?" |
| `get_telemetry` | Aggregate the tool-usage log: which tools get called most, error rates, p50 / p95 latency, dead-surface (declared but never called) |

---

## Adapter status

| `SPEC_SOURCE` | Source | Status | Auth |
|---|---|---|---|
| `markdown_local` | Local `*.md` with YAML-ish frontmatter | ✅ since 0.1.0 | none |
| `github_issues` | GitHub Issues via `gh` CLI | ✅ since 0.1.0 | `gh auth login` or `GITHUB_TOKEN` |
| `linear` | Linear API (GraphQL) | ✅ since 0.2.2 | `LINEAR_API_KEY` + `SPEC_PROJECT_KEY=<team-key>` (optional) |
| `jira` | JIRA Cloud (REST v3, ADF → markdown) | ✅ since 0.2.3 | `JIRA_BASE_URL` + `JIRA_EMAIL` + `JIRA_API_TOKEN` + `SPEC_PROJECT_KEY=<project-key>` (optional) |
| `notion` | Notion databases (REST v1, blocks → markdown) | ✅ since 0.3.0 | `NOTION_TOKEN` + `SPEC_PROJECT_KEY=<database-id>` |
| `figma` | Figma file frames (TEXT nodes + comments → markdown) | ✅ since 0.3.1 | `FIGMA_TOKEN` + `SPEC_PROJECT_KEY=<file-key>` |

---

## Common workflows

Four patterns cover ~90% of real use. Each is one sentence to the AI client; the tools chain automatically.

### 1. Spec → test → run → coverage (the main loop)

> "Fetch LIN-123 from Linear, extract scenarios, generate Playwright tests with mk-qa-master, run them, and update the coverage matrix."

Chains: `fetch_spec` → `parse_spec` → `extract_scenarios` → `mk-qa-master.generate_test` (×N) → `link_test_to_spec` (×N) → `mk-qa-master.run_tests` → `get_coverage_matrix`.

### 2. Spec health check

> "Review every in-progress spec for quality issues and give me a prioritized improvement plan."

Chains: `list_specs(status="in-progress")` → `analyze_spec_quality` → `propose_spec_improvements` → `get_optimization_plan`.

### 3. Rebuild traceability after a refactor

> "Sync the spec ↔ test index from the test source — I just renamed a bunch of files."

Chains: `auto_link_tests` → `get_coverage_matrix`. Tests need `@spec: <ID>` docstring tags for auto-link to work; comment-above-function and docstring-inside both supported.

### 4. Session warmup

> "Before we work on specs today: load the spec-knowledge methodology and tell me which source is active."

Chains: `get_spec_source_info` → `get_spec_context`. Cheap, sets the methodology + adapter context for everything that follows.

---

## Sample output

### `get_optimization_plan` markdown (excerpt)

```markdown
# Optimization plan

_Coverage matrix: 23 spec(s) tracked, 4 untested._
_Spec quality: 23 spec(s) analyzed, 17 finding(s)._
_Drift: 2 drifted, 0 stranded, 5 without ac_hash._

## 🔴 Layer 1 — Coverage gaps

**Specs with zero tests** (ranked first — every business risk lives here):
- `LIN-204` — Apply promo code at checkout
- `LIN-211` — Refund flow

## 🟡 Layer 2 — Spec quality

### `LIN-098` — Checkout latency  (score: 80/100, findings: 4)
- 🟡 `ac-1`: Quantify (e.g., 'response within 200 ms')  (evidence: `fast`)
- 🔴 `ac-3`: Rewrite to describe what the user observes  (evidence: `redis`)

## 🔵 Layer 3 — Process drift

**Drifted** (spec changed since link — review affected tests):
- `LIN-123` — Apply discount at checkout · 4 test(s) potentially stale
```

### `get_coverage_matrix` markdown (excerpt)

```markdown
# Coverage matrix

- Specs tracked: 23
- Specs shown (min_tests=0): 23
- Specs with zero tests: 4

| Spec    | Title                          | Tests | Last status |
|---------|--------------------------------|------:|-------------|
| `LIN-204` | Apply promo code at checkout |     0 | —           |
| `LIN-123` | Apply discount at checkout   |     4 | passed      |
```

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

---

## Why this is missing from the ecosystem

| Tool | Lock-in | What we do differently |
|---|---|---|
| AWS Kiro | AWS IDE only, proprietary | MCP-native, multi-client, open source |
| Jama Connect MCP | $50k+/year, enterprise-only | SMB / indie / AI-native segment |
| GitHub Spec Kit | spec→code; runtime test coverage out of scope | We add runtime test coverage |
| testomat.io / JIRA MCPs | Single source (JIRA), SaaS lock | Multi-source, file-based index, no lock |

See [`docs/prd.md` §4](docs/prd.md) for the full positioning.

## Walkthrough — spec → test → coverage (long form)

Given a Linear ticket *LIN-123 "Apply discount at checkout"* with 4 acceptance criteria:

```
You: Use mk-spec-master to fetch LIN-123, extract scenarios, generate
     Playwright tests with mk-qa-master, run them, and report coverage.
```

The AI client chains:

```
mk-spec-master.fetch_spec("LIN-123")
mk-spec-master.parse_spec(spec_id="LIN-123")        → 4 AC + ac_hash
mk-spec-master.extract_scenarios(...)                → 1 happy + 3 error
mk-spec-master.generate_test_plan(spec_id="LIN-123")

for scenario in plan:
  mk-qa-master.generate_test(business_context=scenario.gherkin)
  mk-spec-master.link_test_to_spec(spec_id="LIN-123", test_node_id=..., ac_hash=...)

mk-qa-master.run_tests
mk-spec-master.get_coverage_matrix
```

The traceability index now records all 4 links with their AC hashes. Next sprint, when the spec changes, `get_drift_report` flags every test whose linked spec has moved — re-run the chain only for those.

---

## Status

| Milestone | Target | Status |
|---|---|---|
| v0.1 (MVP — markdown_local + github_issues, 7 tools) | June 2026 | ✅ Shipped |
| v0.2 (Linear, JIRA, coverage matrix, spec-quality coach, drift report) | Aug 2026 | ✅ Complete (0.2.3) |
| v0.3 (Notion, Figma, auto-link, optimization plan) | Oct 2026 | ✅ Complete (0.3.3) |
| v1.0 (production-ready, docs, integration recipes) | Q4 2026 | ⬜ |

## Family

- [`mk-qa-master`](https://github.com/kao273183/mk-qa-master) — AI 測試大師, the test-runner sibling. Tests run via mk-qa-master; coverage tracked here.
- More `mk-*` MCPs in design (`mk-perf-master`, `mk-a11y-master`).

## License

MIT © 2026 Jack Kao — see [`LICENSE`](LICENSE)
(中文翻譯參考：[`LICENSE.zh-TW.md`](LICENSE.zh-TW.md); the English version is authoritative).

**Plain-English version:** personal use, commercial use, modification, redistribution — all allowed. The only requirement is that you keep the copyright and license notice in your copy. **No warranty**: if it breaks something in production, you can't come after the author.

If this saved you time, [a coffee](https://www.buymeacoffee.com/minikao) goes a long way. ☕
