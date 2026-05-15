<p align="center">
  <img src="https://raw.githubusercontent.com/kao273183/mk-spec-master/main/assets/logo.png" alt="AI 規格大師 logo" width="180" />
</p>

<h1 align="center">AI 規格大師 ｜ MK Spec Master</h1>

<p align="center">
  <em>規格進、場景出。雙向追蹤，永遠知道哪條 spec 被測過。</em>
</p>

<p align="center">
  <a href="README.md">English</a> · <strong>繁體中文</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/mk-spec-master/"><img src="https://img.shields.io/pypi/v/mk-spec-master.svg?logo=pypi&logoColor=white&color=3775A9" alt="PyPI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/status-alpha-orange.svg" alt="Status: Alpha" />
</p>

> 一個 spec-driven testing 的 MCP server。把 Linear / JIRA / GitHub Issues / Notion / Figma / Markdown 上的規格轉成可執行的測試場景、交給 [`mk-qa-master`](https://github.com/kao273183/mk-qa-master) 或任何測試 runner，並維持一份即時的 spec ↔ test 覆蓋矩陣。

> **🟢 Alpha — v0.2 partial。** 10 個 tool 已上線（覆蓋矩陣 + 規格品質教練）。完整設計見 [`docs/prd.md`](docs/prd.md)。v0.2 還缺 Linear / JIRA adapter + drift report。

---

## 安裝

```bash
uvx mk-spec-master    # 或：pip install mk-spec-master
```

MCP client config 加上：

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

接著在 Claude / Cursor / Codex / Gemini CLI 直接說：

> 「用 mk-spec-master 讀 SPEC-001、抽場景、丟給 mk-qa-master 產 Playwright 測試。」

## 這是什麼

一個 MCP server，把規格（Linear ticket、JIRA story、GitHub Issue、Notion 頁、Figma 註解、純 Markdown）轉成結構化測試場景，交給測試 runner（透過 [`mk-qa-master`](https://github.com/kao273183/mk-qa-master) 或其他），並維持即時的 spec ↔ test 覆蓋矩陣。

是 `mk-qa-master` 的姐妹專案，屬於 `mk-*` 系列 AI-QA MCP 家族。

## 為什麼生態圈缺這一塊

| 既有方案 | 鎖住的點 | 我們不同 |
|---|---|---|
| AWS Kiro | 鎖 AWS IDE、閉源 | MCP-native、跨 client、開源 |
| Jama Connect MCP | 一年 $50k+，鎖大企業 | 鎖定 SMB / 獨立開發者 / AI-native |
| GitHub Spec Kit | 只做 spec→code，不碰測試 runtime | 補上 runtime 測試覆蓋 |
| testomat.io / JIRA MCPs | 單一來源（只支援 JIRA）、SaaS lock | 多來源、檔案式 index、零鎖定 |

完整定位表見 [`docs/prd.md` §4](docs/prd.md)。

## Tool 表（v0.2 partial — 10 個 tool）

| Tool | 起始版本 | 用途 |
|---|---|---|
| `get_spec_source_info` | v0.1 | 看目前用哪個 adapter、有哪些可用——session 第一個叫 |
| `list_specs` | v0.1 | 列目前 source 內的 specs（可按 status / label / limit 過濾） |
| `fetch_spec` | v0.1 | 依 id 拉單一 spec 完整內容 |
| `parse_spec` | v0.1 | 啟發式抽 AC（支援英文 + 繁中 + 簡中 標題格式）；可以給 `spec_id` 或 `raw_text` |
| `extract_scenarios` | v0.1 | AC → 場景，分 happy / edge / error（負面前綴感知，不會誤把 "non-expired" 算 error）+ 盡力產 Given/When/Then |
| `generate_test_plan` | v0.1 | 一鍵 fetch + parse + extract → markdown 計畫，每個場景一個 `business_context:` 區塊，直接餵 `mk-qa-master.generate_test` |
| `link_test_to_spec` | v0.1 | 記錄某 test 對應某 spec（寫進 `SPEC_PROJECT_ROOT/.mk-spec-master/index.json`）。v0.2 開始可以順手帶 title / source / url 進來給矩陣顯示 |
| `get_coverage_matrix` | **v0.2** | spec × test 覆蓋矩陣——一次回答「哪些 spec 沒被測」 |
| `analyze_spec_quality` | **v0.2** | 啟發式教練——抓模糊用詞、實作細節洩漏、未定義的角色（這就是相對 Kiro / Spec Kit 的差異化護城河） |
| `propose_spec_improvements` | **v0.2** | 把 analyze 輸出整理成 PM 可直接照做的 markdown 改寫建議 |

v0.2 還在做的：`get_drift_report` + Linear / JIRA adapter。

## Adapter 狀態

| `SPEC_SOURCE` | 來源 | 狀態 | 認證 |
|---|---|---|---|
| `markdown_local` | 本地 `*.md`，frontmatter 帶 metadata | ✅ 0.1.0 起 | 不用 |
| `github_issues` | GitHub Issues，走 `gh` CLI | ✅ 0.1.0 起 | `gh auth login` 或 `GITHUB_TOKEN` |
| `linear` | Linear API | ⏳ 待補 — v0.2.x | `LINEAR_API_KEY` |
| `jira` | JIRA Cloud / Server | ⏳ 待補 — v0.2.x | `JIRA_API_TOKEN` + `JIRA_BASE_URL` |
| `notion` | Notion databases | ⏳ 規劃中 — v0.3 | `NOTION_TOKEN` |
| `figma` | Figma 註解 + comments | ⏳ 規劃中 — v0.3 | `FIGMA_TOKEN` |

> v0.2.0 ship 的是覆蓋矩陣 + 規格品質教練 tools，沒有新 adapter。Linear / JIRA adapter 排在後續 0.2.x。

## 範例流程——spec → test → coverage

假設 Linear 上有票 *LIN-123「結帳套用折扣碼」*，4 條驗收條件：

```
你：用 mk-spec-master 抓 LIN-123、抽場景、丟給 mk-qa-master 產 Playwright
    測試、跑起來、回報覆蓋率。
```

AI client 自動串：

```
mk-spec-master.fetch_spec("LIN-123")
mk-spec-master.parse_spec(spec_id="LIN-123")        → 4 條 AC
mk-spec-master.extract_scenarios(...)                → 1 happy + 3 error
mk-spec-master.generate_test_plan(spec_id="LIN-123")

每個 scenario：
  mk-qa-master.generate_test(business_context=scenario.gherkin)
  mk-spec-master.link_test_to_spec(spec_id="LIN-123", test_node_id=...)

mk-qa-master.run_tests
```

Traceability index 已記下 4 條對應。下個 sprint 規格改了時，v0.2 的 `get_drift_report` 會自動標出可能過期的 test。

## 開發進度

| 里程碑 | 目標 | 狀態 |
|---|---|---|
| v0.1（MVP — markdown_local + github_issues、7 tools） | 2026/06 | ✅ Shipped |
| v0.2（Linear、JIRA、覆蓋矩陣、規格品質教練） | 2026/08 | 🟡 覆蓋矩陣 + 教練已 ship（0.2.0）；Linear / JIRA + drift report 待補 |
| v0.3（Notion、Figma、自動 link、optimization plan） | 2026/10 | ⬜ |
| v1.0（production-ready、完整文件、整合範例） | 2026 Q4 | ⬜ |

## 家族

- [`mk-qa-master`](https://github.com/kao273183/mk-qa-master) — AI 測試大師，跑測試的姐妹專案。實際執行靠它，覆蓋率追蹤靠這裡。
- 後續規劃中：`mk-perf-master`、`mk-a11y-master` 等。

## License

MIT — 見 [LICENSE](LICENSE)。
