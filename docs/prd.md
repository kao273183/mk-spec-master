# mk-spec-master — MVP PRD

**Status:** Draft v0.1 · **Author:** Jack Kao (kao273183) · **Last updated:** 2026-05-15

---

## 1. Vision

> **Specs in, scenarios out. Bidirectional traceability so you always know what's tested.**

The MCP that turns specs (PRDs, Linear / JIRA / GitHub Issues / Notion / Figma comments) into structured test scenarios, feeds them to any test runner via mk-qa-master, and maintains a live spec ↔ test coverage matrix.

Chinese brand: **AI 規格大師** (family member of 「AI 大師」 series alongside mk-qa-master).

---

## 2. Problem Statement

Three failure modes the industry has lived with for decades:

1. **Specs decay** — PRD says 30 acceptance criteria, engineering implements 25, QA tests 18. Three weeks later, nobody can answer "is this AC tested?"
2. **Drift goes invisible** — spec changes, test doesn't follow (or vice versa). The mismatch eats teams alive, surfaces only in production incidents.
3. **Spec quality varies wildly** — "should be fast", "should be intuitive" — vague AC produce vague tests. No tool flags this *before* the code is written.

AI coding agents made these worse, not better — they generate code from vague specs, write tests that pass but don't validate intent, then move on.

**Hypothesis:** the SDD movement (Spec-Driven Development, mainstream in 2025–2026) created demand for tools that close the spec ↔ test loop. Most existing SDD tooling closes spec → code; the test side is underserved.

---

## 3. Why now

SDD entered mainstream in 2025–2026:

- **GitHub Spec Kit** (open-source CLI) released, integrates with Copilot/Claude Code/Cursor
- **AWS Kiro** (spec-native AI IDE) GA
- **Anthropic** publishes the "prompt → spec → code" canonical loop
- **EARS** (Easy Approach to Requirements Syntax) reports 3–10× higher AI first-pass success on non-trivial tasks
- Enterprise procurement teams now require traceability for AI-generated code (compliance)

The window for an opinionated open-source MCP in this space is **6–12 months** before larger platforms absorb it.

---

## 4. Competitive Positioning

| Tool | What it does | Lock-in | Our angle |
|---|---|---|---|
| **GitHub Spec Kit** | spec → design → tasks → code (open source CLI) | None, but spec→test runtime is out of scope | We do what they don't: runtime test coverage |
| **AWS Kiro** | spec ↔ test traceability + Test Generator | AWS-locked, IDE-bound, proprietary | We're MCP-native, multi-IDE, open source |
| **Jama Connect MCP** | Enterprise requirements traceability | $50k+/year, FDA/aerospace target | We target the SMB/indie/AI-native segment |
| **testomat.io / kushb05 JIRA MCP** | JIRA ticket → test case | Single source (JIRA), SaaS lock | Multi-source (Linear/JIRA/GitHub/Notion/Markdown/Figma) |
| **formulahendry/spec-dev MCP** | Prompts/templates for SDD workflow | None, but no test layer | We add the test runtime + coverage matrix |

**Our defensible position:**

> The only **MCP-native, open-source, multi-source, runner-agnostic** spec→test bridge with a built-in **spec-quality coach** layer.

Five differentiators no competitor has all of:
1. Multi-source adapter pattern (5+ spec sources, one MCP interface)
2. File-based traceability index (user owns the data, no SaaS lock)
3. Spec quality coach (`analyze_spec_quality` / `propose_spec_improvements`)
4. Bidirectional drift detection
5. Composes cleanly with mk-qa-master AND any other test MCP

---

## 5. Target Users

**Primary:** Solo developers + small QA teams (1–5 people) using Claude Code / Cursor / Codex / Gemini CLI for AI-assisted development. They feel the spec-test gap acutely because they own the whole loop themselves.

**Secondary:** Mid-size product teams (PM + 3–10 engineers + 1–2 QA) who want traceability without paying enterprise prices for Jama.

**Anti-personas:**
- Regulated enterprise (FDA, aerospace) — go buy Jama
- Pure no-code shops — they don't have specs in the SDD sense

---

## 6. MVP Scope (v0.1)

**In scope:**
- 2 adapters: `markdown_local` + `github_issues`
- 7 core tools (see §8 — flagged "MVP")
- File-based traceability index at `SPEC_PROJECT_ROOT/.mk-spec-master/index.json`
- Manual `link_test_to_spec` (no auto-inference yet)
- README + `docs/prd.md` (this doc) + 1 walkthrough example
- PyPI publish via Trusted Publishing (mirror mk-qa-master's `publish.yml`)

**Explicitly out of scope (deferred to later versions):**
- Linear / JIRA / Notion / Figma adapters → v0.2 / v0.3
- Auto-inference of test↔spec links → v0.2
- Spec quality coach (`analyze_spec_quality`) → v0.2
- Drift detection beyond hash comparison → v0.2
- `get_optimization_plan` coach output → v0.2
- Web UI / dashboard → not planned (CLI + MCP only)

**MVP timeline target:** ship to PyPI within 4 weeks of starting code.

---

## 7. System Architecture

```
mk-spec-master/
├── pyproject.toml              # name: mk-spec-master, module: mk_spec_master
├── README.md
├── README.zh-TW.md
├── smithery.yaml               # stdio config
├── Dockerfile                  # Glama introspection
├── .github/
│   └── workflows/
│       └── publish.yml         # mirror mk-qa-master's
├── docs/
│   ├── prd.md                  # this file
│   ├── framework.md            # design notes (post-MVP)
│   └── walkthrough.md          # end-to-end example
├── src/mk_spec_master/
│   ├── __init__.py
│   ├── server.py               # MCP entry, tool routing
│   ├── config.py               # env vars, paths
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py             # SpecSource ABC
│   │   ├── markdown_local.py   # MVP
│   │   └── github_issues.py    # MVP
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── ac_extractor.py     # natural lang → structured AC
│   │   └── scenario_builder.py # AC → test scenarios
│   ├── index/
│   │   ├── __init__.py
│   │   └── traceability.py     # JSON index read/write
│   ├── tools/                  # one file per tool group
│   │   ├── __init__.py
│   │   ├── specs.py            # list_specs, fetch_spec, parse_spec
│   │   ├── scenarios.py        # extract_scenarios, generate_test_plan
│   │   ├── coverage.py         # link_test_to_spec, get_coverage_matrix
│   │   └── meta.py             # get_spec_source_info
│   └── prompts/                # EARS templates, AC extraction prompts
└── examples/
    ├── sample-specs/           # markdown specs for dogfooding
    └── configs/                # client config snippets
```

---

## 8. Tool Surface

Target: 12–14 tools at v0.2 maturity. MVP ships with 7.

| Tool | MVP? | Purpose |
|---|---|---|
| `get_spec_source_info` | ✅ | Active adapter + all available; mirrors `mk-qa-master.get_runner_info` |
| `list_specs` | ✅ | List specs (filter by status / label / sprint / source-specific keys) |
| `fetch_spec` | ✅ | Pull one spec's full content by id/url |
| `parse_spec` | ✅ | Natural language → structured AC[] (in EARS format where possible) |
| `extract_scenarios` | ✅ | AC[] → test scenarios (Given/When/Then, with happy/edge/error tags) |
| `generate_test_plan` | ✅ | Markdown plan ready for `mk-qa-master.generate_test(business_context=...)` |
| `link_test_to_spec` | ✅ | Register "test X tests spec Y" mapping |
| `get_coverage_matrix` | v0.2 | spec × test grid; the killer view |
| `get_drift_report` | v0.2 | spec changed-test didn't / test orphaned |
| `analyze_spec_quality` | v0.2 | Heuristics: vague AC, missing edge cases, conflicting clauses |
| `propose_spec_improvements` | v0.2 | Rewrite suggestions for PM |
| `init_spec_knowledge` / `get_spec_context` | v0.3 | Domain methodology layer (mirrors mk-qa) |
| `get_optimization_plan` | v0.3 | 3-layer coach: coverage / quality / process |
| `auto_link_tests` | v0.3 | Infer test↔spec from test docstrings / commit messages |

**Tool signatures (MVP only, full schemas in `src/mk_spec_master/server.py`):**

```python
get_spec_source_info() -> { active: str, available: list[str] }

list_specs(
    status: str | None = None,
    label: str | None = None,
    limit: int = 50
) -> list[SpecSummary]

fetch_spec(id: str) -> Spec  # id format depends on source

parse_spec(
    spec_id: str | None = None,    # use fetched spec
    raw_text: str | None = None    # or ad-hoc text
) -> { acceptance_criteria: list[AC], roles: list[str], preconditions: list[str] }

extract_scenarios(
    acceptance_criteria: list[AC]
) -> list[Scenario]
    # Scenario = { title, given, when, then, kind: 'happy'|'edge'|'error' }

generate_test_plan(
    spec_id: str,
    target_runner: str = "pytest"  # hint passed downstream
) -> { markdown: str, scenarios: list[Scenario] }

link_test_to_spec(
    spec_id: str,
    test_node_id: str   # e.g. "tests/test_checkout.py::test_apply_discount"
) -> { linked: bool, total_links_for_spec: int }
```

---

## 9. Data Model

**Traceability index** stored at `SPEC_PROJECT_ROOT/.mk-spec-master/index.json`:

```json
{
  "version": 1,
  "specs": {
    "LIN-123": {
      "source": "linear",
      "title": "Apply discount at checkout",
      "url": "https://linear.app/...",
      "ac_hash": "sha256:abc123...",
      "last_synced": "2026-05-15T13:34:50Z",
      "linked_tests": [
        {
          "node_id": "tests/test_checkout.py::test_apply_discount",
          "linked_at": "2026-05-15T13:34:50Z",
          "last_status": "passed",
          "last_run": "2026-05-15T13:34:50Z"
        }
      ]
    }
  },
  "orphans": [
    {
      "test_node_id": "tests/test_legacy.py::test_old_flow",
      "first_seen": "2026-05-10T...",
      "reason": "no_spec_linked"
    }
  ]
}
```

**Why `ac_hash`:** drift detection compares hashes, no full-text diff per check. Cheap.

**Why `orphans`:** explicit "this test has no spec" list pressures teams to either delete the test or link it.

---

## 10. Adapter Design

Mirrors mk-qa-master's `runners/` abstraction.

```python
# src/mk_spec_master/adapters/base.py

class SpecSource(ABC):
    @abstractmethod
    def list_specs(self, **filters) -> list[SpecSummary]: ...

    @abstractmethod
    def fetch(self, spec_id: str) -> Spec: ...

    @property
    @abstractmethod
    def name(self) -> str: ...
```

**Env var:** `SPEC_SOURCE` selects active adapter (one per process, like `QA_RUNNER`).

**MVP adapters:**

| Adapter | `SPEC_SOURCE` | Auth | Notes |
|---|---|---|---|
| `markdown_local` | `markdown_local` | None | Reads `SPEC_PROJECT_ROOT/specs/*.md`, frontmatter-driven |
| `github_issues` | `github_issues` | `GITHUB_TOKEN` env or `gh` CLI on PATH | `SPEC_PROJECT_KEY=owner/repo` |

**v0.2 adapters:**
- `linear` (`LINEAR_API_KEY`, `SPEC_PROJECT_KEY=team-id`)
- `jira` (`JIRA_API_TOKEN` + `JIRA_BASE_URL` + `SPEC_PROJECT_KEY=board-id`)

**v0.3 adapters:**
- `notion` (`NOTION_TOKEN`, `SPEC_PROJECT_KEY=database-id`)
- `figma` (`FIGMA_TOKEN`, `SPEC_PROJECT_KEY=file-id`) — annotations + comments

---

## 11. Integration with mk-qa-master

**No MCP-to-MCP RPC** (not in the protocol). The AI client orchestrates the chain across the two MCP servers.

Canonical chain in a Claude / Cursor session:

```
1. mk-spec-master.list_specs(status="in-progress")
2. mk-spec-master.fetch_spec(id="LIN-123")
3. mk-spec-master.parse_spec(spec_id="LIN-123")
4. mk-spec-master.extract_scenarios(acceptance_criteria=...)
5. for each scenario:
     mk-qa-master.generate_test(
       module=...,                           # optional, from analyze_url/analyze_screen
       business_context=scenario.gherkin     # ← key bridge param
     )
     → returns test_node_id

6. mk-spec-master.link_test_to_spec(
     spec_id="LIN-123",
     test_node_id=<returned>
   )

7. mk-qa-master.run_tests
8. mk-spec-master.get_coverage_matrix
   → "LIN-123: 4/5 AC covered (last run: passed)"
```

**Key design move:** mk-qa-master *already has* `business_context` as a `generate_test` parameter. We piggyback on that, no mk-qa-master changes needed for v0.1.

**v0.2 enhancement:** add `spec_id` parameter to `mk-qa-master.generate_test` so mk-qa records the linkage automatically (eliminates step 6). Requires a minor PR upstream.

---

## 12. Coach Layer (the differentiator)

Deferred to v0.2 but **central to the moat**. Without this, mk-spec-master is just another "JIRA → test case" tool.

Three coach outputs from `get_optimization_plan`:

**Layer 1 — Coverage gaps**
- Specs with zero linked tests, ranked by business priority label
- Specs covered only by happy-path scenarios (no edge / error)
- Sprint-scoped: which in-progress specs are still untested

**Layer 2 — Spec quality** (this is the virgin territory)
- **Vague language detector**: flag specs containing "fast", "easy", "intuitive", "user-friendly", "modern" without measurable thresholds
- **Missing preconditions**: AC reference user state ("logged-in user") without defining how to set up that state
- **Conflicting AC across specs**: spec A says X, spec B says ¬X — flag the pair
- **Untestable AC**: AC that describe internal architecture instead of user-observable behavior

**Layer 3 — Process drift**
- Specs modified >7 days ago with no test update
- Tests modified >14 days ago with no spec update
- Orphan ratio trend (week over week)
- Stale links (test deleted but link still in index)

Output format: same as mk-qa-master's `optimization-plan.md` — flat markdown, ranked actions, evidence inline.

---

## 13. Non-functional Requirements

| Concern | Requirement |
|---|---|
| **Privacy** | Spec content stays local. No telemetry by default. All LLM calls go through the AI client (Claude/etc), not directly from this server. Explicit `--local-only` flag disables any future external calls. |
| **Performance** | `list_specs` < 2s for 500 specs cached. `parse_spec` depends on AI client speed (no control here). Index reads < 100ms. |
| **Storage** | Index JSON < 10MB for projects with <10k specs. SQLite migration deferred to v0.3 if needed. |
| **Auth** | Adapter-specific. Tokens read from env vars only. Never logged. |
| **Errors** | All adapter failures return structured `{error, retryable, hint}` shape (mirror mk-qa-master). |
| **Compatibility** | Python 3.10+, MCP SDK >=1.0.0, mirror mk-qa-master's stack |

---

## 14. Roadmap

| Milestone | Scope | Target |
|---|---|---|
| **v0.1 (MVP)** | 2 adapters, 7 tools, manual linking, file-based index, PyPI publish | 4 weeks |
| **v0.2** | Linear + JIRA adapters, coverage matrix UI in markdown, drift report, spec quality coach | +6 weeks |
| **v0.3** | Notion + Figma, auto-link via test docstrings, `get_optimization_plan`, Smithery + Glama parity | +8 weeks |
| **v1.0** | Production-ready: comprehensive docs, walkthrough videos, integration recipes for Claude/Cursor/Codex/Gemini, blog series complete | Q4 2026 |

---

## 15. Open Questions / Risks

| # | Question | Mitigation plan |
|---|---|---|
| Q1 | Should we use EARS as the canonical AC format internally? | Yes for parser output. Allow free-form input, normalize on parse. |
| Q2 | How to handle non-English specs (中文 PRD)? | LLM call passes through AI client → multilingual by default. Test on Chinese spec corpus before v0.2. |
| Q3 | Should `get_coverage_matrix` output JSON or markdown? | Both. JSON for AI client to query, markdown for human-readable report. |
| Q4 | Should test↔spec links live in the test file (docstring `@spec: LIN-123`) or only in the index? | Both. Index is canonical. Docstring is the rebuild source — if index lost, scan tests for `@spec:` tags to rebuild. |
| R1 | Kiro releases an MCP shim — copies our positioning | v0.1 ships fast (4 weeks), establish reputation before Kiro pivots |
| R2 | GitHub Spec Kit adds runtime test coverage natively | Watch their roadmap; if signaled, accelerate `analyze_spec_quality` (their weakest area) |
| R3 | LLM-driven `parse_spec` returns garbage on poorly-written specs | First adapter is `markdown_local` (controlled corpus) → tune prompts → then expand |

---

## 16. Success Metrics

**Adoption (3 months from v0.1):**
- 100 GitHub stars on the repo
- 1,000 PyPI downloads / month
- 10 unsolicited Issues / PRs from external users
- Mentioned in 1 SDD blog post / podcast / conference talk

**Quality (any time):**
- 70%+ of users surveyed report `get_coverage_matrix` is "useful daily" or "useful weekly"
- 0 critical bugs (data loss, index corruption) reported
- Glama quality grade ≥ B (parity with mk-qa-master baseline)

**Family effect (6 months):**
- 30%+ of mk-qa-master users also install mk-spec-master (measured via Claude Desktop config telemetry where opted in)
- The `mk-*` family namespace becomes a recognizable brand in MCP circles

---

## 17. Open Source Strategy

- License: MIT (mirror mk-qa-master)
- Repo: `github.com/kao273183/mk-spec-master`
- Branch protection on main, signed releases
- Trusted Publishing to PyPI (same setup as mk-qa-master)
- Smithery + Glama listed within 2 weeks of v0.1
- awesome-mcp-servers PR submitted on v0.1 release day
- Single blog post (positioning piece) on launch day; Show HN within 1 week

---

## 18. Naming

| Surface | Value |
|---|---|
| PyPI / npm | `mk-spec-master` |
| Python module | `mk_spec_master` |
| CLI command | `mk-spec-master` |
| MCP Server() id | `mk-spec-master` |
| Display name (EN) | MK Spec Master |
| Display name (中) | AI 規格大師 |
| Tagline | Specs in, scenarios out. Bidirectional traceability so you always know what's tested. |
| Family slot | `mk-*` series (after `mk-qa-master`, before `mk-perf-master` / `mk-a11y-master`) |

---

## 19. Appendix: Sample Walkthrough

A user has a Linear ticket "LIN-123: Apply discount at checkout". They want to ship the feature with full spec→test coverage.

**Step 1 — Define spec.** Linear ticket already exists with AC:
> 1. Logged-in user enters valid promo code → discount applied to subtotal
> 2. Invalid promo code → inline error "Promo code not recognized"
> 3. Expired promo code → inline error "This code has expired"
> 4. Promo code applied + cart empty → error "Add items to your cart first"

**Step 2 — In Claude (Cursor / Codex / Gemini):**
> "Use mk-spec-master to fetch LIN-123, extract scenarios, generate Playwright tests with mk-qa-master, run them, and report coverage."

**Step 3 — AI orchestrates:**
```
mk-spec-master.fetch_spec("LIN-123")
mk-spec-master.parse_spec(spec_id="LIN-123")
  → 4 ACs, 1 role (logged-in user), 1 precondition (items in cart for AC1)
mk-spec-master.extract_scenarios(...)
  → 4 scenarios (1 happy + 3 error)
mk-spec-master.generate_test_plan(spec_id="LIN-123", target_runner="pytest")
  → markdown plan ready for handoff

for each scenario:
  mk-qa-master.generate_test(business_context=scenario.gherkin)
    → tests/test_discount.py::test_valid_promo
    → tests/test_discount.py::test_invalid_promo
    → tests/test_discount.py::test_expired_promo
    → tests/test_discount.py::test_empty_cart_promo

for each test:
  mk-spec-master.link_test_to_spec("LIN-123", node_id)

mk-qa-master.run_tests
  → 4/4 passed

mk-spec-master.get_coverage_matrix
  → "LIN-123: 4/4 AC covered. All passing."
```

**Step 4 — A week later, PM changes AC2 to also reject codes shorter than 4 chars.** Linear ticket updated.

**Next time the team runs `mk-spec-master.get_drift_report`:**
> "LIN-123 spec changed (ac_hash mismatch). Test `test_invalid_promo` may be stale — re-extract scenarios and update test."

This is the loop. **mk-qa-master alone tells you what passes. mk-qa-master + mk-spec-master tells you what is *correct*.**

---

*End of PRD v0.1. Revisions tracked in git. Discuss in Issues at github.com/kao273183/mk-spec-master.*
