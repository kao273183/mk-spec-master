<h1 align="center">MK Spec Master</h1>

<p align="center">
  <em>AI 規格大師 — specs in, scenarios out. Bidirectional traceability so you always know what's tested.</em>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/status-pre--alpha-orange.svg" alt="Status: Pre-alpha" />
</p>

> **⚠️ Pre-alpha skeleton.** Architecture and PRD defined in [`docs/prd.md`](docs/prd.md). No MVP functionality shipped yet. First release target: 4 weeks from scaffold (mid-June 2026).

---

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

## Status

| Milestone | Target | Status |
|---|---|---|
| v0.1 (MVP — markdown_local + github_issues, 7 tools) | June 2026 | 🟡 In progress |
| v0.2 (Linear, JIRA, coverage matrix, spec-quality coach) | Aug 2026 | ⬜ |
| v0.3 (Notion, Figma, auto-link, optimization plan) | Oct 2026 | ⬜ |
| v1.0 (production-ready, docs, integration recipes) | Q4 2026 | ⬜ |

## Quick design read

- **Vision + problem**: [`docs/prd.md` §1–2](docs/prd.md)
- **Competitive positioning**: [`docs/prd.md` §4](docs/prd.md)
- **Tool surface**: [`docs/prd.md` §8](docs/prd.md)
- **Walkthrough (end-to-end with mk-qa-master)**: [`docs/prd.md` §19](docs/prd.md)

## Related

- [mk-qa-master](https://github.com/kao273183/mk-qa-master) — the QA loop sibling. Tests run via mk-qa-master; coverage tracked here.

## License

MIT — see [LICENSE](LICENSE).
