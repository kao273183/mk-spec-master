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

> **🟢 Alpha — v0.3 完成。** **15 個 tool** + 6 個 adapter。完整設計見 [`docs/prd.md`](docs/prd.md)。下一站：v1.0（文件硬化、整合範例、production-ready）。

---

## 這是什麼

一個 MCP server，把規格（Linear ticket、JIRA story、GitHub Issue、Notion 頁、Figma 註解、純 Markdown）轉成結構化測試場景，交給測試 runner（透過 [`mk-qa-master`](https://github.com/kao273183/mk-qa-master) 或其他），並維持即時的 spec ↔ test 覆蓋矩陣。

是 `mk-qa-master` 的姐妹專案，屬於 `mk-*` 系列 AI-QA MCP 家族。

## 這「不是」什麼

| 不是 | 你應該用 |
|---|---|
| spec **編輯器** | Linear / JIRA / Notion / Markdown — 規格寫在你原本就用的地方 |
| **測試 runner** | [`mk-qa-master`](https://github.com/kao273183/mk-qa-master)（pytest / Jest / Cypress / Go test / Maestro） |
| **issue tracker UI** | Linear / JIRA / Notion 各自的原生介面 |
| **spec → code** 生成器 | GitHub Spec Kit、AWS Kiro |
| **LLM** | 推理交給你的 AI client（Claude / Cursor / Codex / Gemini） |

mk-spec-master 站在**規格來源跟測試 runner 之間**——純做 *spec ↔ test* 對應、上層的覆蓋矩陣，跟同時為兩端打分的品質教練。

---

## Tool 表（15 個）

依角色分組。每組是 spec→test→coverage→coach 流水線的一層。

### Meta — 暖機（1）

| Tool | 用途 |
|---|---|
| `get_spec_source_info` | 看目前用哪個 adapter、有哪些可用——session 第一個叫，AI 才知道後面該預期 Linear / JIRA / Notion / Figma / Markdown 的語意 |

### Discovery — 找跟讀規格（3）

| Tool | 用途 |
|---|---|
| `list_specs` | 列目前 source 內的 specs（可按 status / label / limit 過濾） |
| `fetch_spec` | 依 id 拉單一 spec 完整內容 |
| `parse_spec` | 啟發式抽 AC（支援英文 + 繁中 + 簡中 標題格式）；可以給 `spec_id` 或 `raw_text`。回傳 `_meta.ac_hash` 給 drift detection 用 |

### Generation — 規格變可測物件（2）

| Tool | 用途 |
|---|---|
| `extract_scenarios` | AC → 場景，分 happy / edge / error（負面前綴感知，不會誤把 "non-expired" 算 error）+ 盡力產 Given/When/Then |
| `generate_test_plan` | 一鍵 fetch + parse + extract → markdown 計畫，每個場景一個 `business_context:` 區塊，直接餵 `mk-qa-master.generate_test` |

### Coverage & drift — 追蹤層（4）

| Tool | 用途 |
|---|---|
| `link_test_to_spec` | 記錄某 test 對應某 spec（寫進 `SPEC_PROJECT_ROOT/.mk-spec-master/index.json`）。也快取 title / source / url / ac_hash 給矩陣跟 drift report |
| `auto_link_tests` | 掃 test 資料夾抓 `@spec: <ID>` tag 自動 link。支援 Python / JS / TS / Go，`dry_run` 預覽 |
| `get_coverage_matrix` | spec × test 覆蓋矩陣——一次回答「哪些 spec 沒被測」 |
| `get_drift_report` | 對每個有存 ac_hash 的 spec 重新 fetch 比對，分 fresh / drifted / unknown / stranded 四格 |

### Coach — 品質 + 排序（3）

| Tool | 用途 |
|---|---|
| `analyze_spec_quality` | 啟發式教練——抓模糊用詞、實作細節洩漏、未定義的角色（相對 Kiro / Spec Kit 的差異化護城河） |
| `propose_spec_improvements` | 把 analyze 輸出整理成 PM 可直接照做的 markdown 改寫建議 |
| `get_optimization_plan` | 三層整合 coach markdown：Layer 1 覆蓋缺口、Layer 2 規格品質、Layer 3 流程飄移。「下一步該修什麼」就叫這個 |

### Knowledge — 領域知識（2）

| Tool | 用途 |
|---|---|
| `init_spec_knowledge` | 在 `SPEC_PROJECT_ROOT/spec-knowledge.md` 寫一份起始模板（EARS / INVEST / AC 品質規則 + 你的 domain rules / actors / glossary TODO 區段）。冪等不會覆蓋 |
| `get_spec_context` | 讀 spec-knowledge 檔（沒有的話走 built-in 預設）。可帶 `section` 抓單一段落。session 開頭叫，把方法論帶進每次互動 |

---

## Adapter 狀態

| `SPEC_SOURCE` | 來源 | 狀態 | 認證 |
|---|---|---|---|
| `markdown_local` | 本地 `*.md`，frontmatter 帶 metadata | ✅ 0.1.0 起 | 不用 |
| `github_issues` | GitHub Issues，走 `gh` CLI | ✅ 0.1.0 起 | `gh auth login` 或 `GITHUB_TOKEN` |
| `linear` | Linear API（GraphQL） | ✅ 0.2.2 起 | `LINEAR_API_KEY` + `SPEC_PROJECT_KEY=<團隊代碼>`（選填） |
| `jira` | JIRA Cloud（REST v3、ADF → markdown） | ✅ 0.2.3 起 | `JIRA_BASE_URL` + `JIRA_EMAIL` + `JIRA_API_TOKEN` + `SPEC_PROJECT_KEY=<專案 key>`（選填） |
| `notion` | Notion databases（REST v1、blocks → markdown） | ✅ 0.3.0 起 | `NOTION_TOKEN` + `SPEC_PROJECT_KEY=<database-id>` |
| `figma` | Figma frames（TEXT 節點 + comments → markdown） | ✅ 0.3.1 起 | `FIGMA_TOKEN` + `SPEC_PROJECT_KEY=<file-key>` |

---

## 常用 workflow

四個 prompt pattern 涵蓋 ~90% 的真實情境。每個都只是一句話交給 AI client，工具會自動串。

### 1. Spec → test → run → coverage（主迴圈）

> 「用 mk-spec-master 抓 LIN-123、抽場景，丟 mk-qa-master 產 Playwright 測試、跑起來、更新覆蓋矩陣。」

串：`fetch_spec` → `parse_spec` → `extract_scenarios` → `mk-qa-master.generate_test`（×N）→ `link_test_to_spec`（×N）→ `mk-qa-master.run_tests` → `get_coverage_matrix`。

### 2. 規格體檢

> 「把所有 in-progress 的 spec 都做品質檢查，給我優先級改善計畫。」

串：`list_specs(status="in-progress")` → `analyze_spec_quality` → `propose_spec_improvements` → `get_optimization_plan`。

### 3. 重整 traceability（重構後重建索引）

> 「我剛重新命名一堆 test 檔——掃 source tree 把 spec↔test 索引重建一次。」

串：`auto_link_tests` → `get_coverage_matrix`。test 要寫 `@spec: <ID>` 在 docstring 或註解，自動 link 才認得。

### 4. Session 暖機

> 「進規格工作前：把 spec-knowledge 方法論載入，告訴我目前用的是哪個 source。」

串：`get_spec_source_info` → `get_spec_context`。便宜，把方法論 + adapter 上下文準備好給後面所有互動。

---

## 範例輸出

### `get_optimization_plan` markdown（節錄）

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

### `get_coverage_matrix` markdown（節錄）

```markdown
# Coverage matrix

- Specs tracked: 23
- Specs shown (min_tests=0): 23
- Specs with zero tests: 4

| Spec      | Title                          | Tests | Last status |
|-----------|--------------------------------|------:|-------------|
| `LIN-204` | Apply promo code at checkout   |     0 | —           |
| `LIN-123` | Apply discount at checkout     |     4 | passed      |
```

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

---

## 為什麼生態圈缺這一塊

| 既有方案 | 鎖住的點 | 我們不同 |
|---|---|---|
| AWS Kiro | 鎖 AWS IDE、閉源 | MCP-native、跨 client、開源 |
| Jama Connect MCP | 一年 $50k+，鎖大企業 | 鎖定 SMB / 獨立開發者 / AI-native |
| GitHub Spec Kit | 只做 spec→code，不碰測試 runtime | 補上 runtime 測試覆蓋 |
| testomat.io / JIRA MCPs | 單一來源（只支援 JIRA）、SaaS lock | 多來源、檔案式 index、零鎖定 |

完整定位表見 [`docs/prd.md` §4](docs/prd.md)。

## 完整 walkthrough — spec → test → coverage

假設 Linear 上有票 *LIN-123「結帳套用折扣碼」*，4 條驗收條件：

```
你：用 mk-spec-master 抓 LIN-123、抽場景、丟給 mk-qa-master 產 Playwright
    測試、跑起來、回報覆蓋率。
```

AI client 自動串：

```
mk-spec-master.fetch_spec("LIN-123")
mk-spec-master.parse_spec(spec_id="LIN-123")        → 4 條 AC + ac_hash
mk-spec-master.extract_scenarios(...)                → 1 happy + 3 error
mk-spec-master.generate_test_plan(spec_id="LIN-123")

每個 scenario：
  mk-qa-master.generate_test(business_context=scenario.gherkin)
  mk-spec-master.link_test_to_spec(spec_id="LIN-123", test_node_id=..., ac_hash=...)

mk-qa-master.run_tests
mk-spec-master.get_coverage_matrix
```

Traceability index 已記下 4 條對應（連 ac_hash 一起存）。下個 sprint 規格改了時，`get_drift_report` 會自動標出哪些 test 對應的 spec 飄掉了，只重跑那一小段就好。

---

## 開發進度

| 里程碑 | 目標 | 狀態 |
|---|---|---|
| v0.1（MVP — markdown_local + github_issues、7 tools） | 2026/06 | ✅ Shipped |
| v0.2（Linear、JIRA、覆蓋矩陣、規格品質教練、drift report） | 2026/08 | ✅ 完整 ship（0.2.3） |
| v0.3（Notion、Figma、auto-link、optimization plan） | 2026/10 | ✅ 完整 ship（0.3.3） |
| v1.0（production-ready、完整文件、整合範例） | 2026 Q4 | ⬜ |

## 家族

- [`mk-qa-master`](https://github.com/kao273183/mk-qa-master) — AI 測試大師，跑測試的姐妹專案。實際執行靠它，覆蓋率追蹤靠這裡。
- 後續規劃中：`mk-perf-master`、`mk-a11y-master` 等。

## License

MIT © 2026 Jack Kao — 英文原版（具法律效力）見 [`LICENSE`](LICENSE)；
中文翻譯參考見 [`LICENSE.zh-TW.md`](LICENSE.zh-TW.md)。

**白話版：** 個人用、商用、改寫、再散布都可以，**唯一要求是保留 copyright 跟授權聲明在你的 copy 裡**。**不附保證**：上 production 出事自負，不能反過來告作者。

如果這專案幫到你，[請我喝杯咖啡](https://www.buymeacoffee.com/minikao)。☕
