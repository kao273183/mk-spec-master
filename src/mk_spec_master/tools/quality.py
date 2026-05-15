"""Spec-quality coach — analyze_spec_quality + propose_spec_improvements.

The differentiator vs Kiro / Spec Kit / Jama. Those tools assume specs
are well-written; this tool *checks* whether they are.

v0.2 ships three heuristics:
    1. Vague language    — adjectives without measurable thresholds
    2. Untestable AC     — describes implementation, not user-observable behaviour
    3. Unclear role refs — references "logged-in user" etc. without defining them

Heuristics are intentionally conservative — false negatives are cheaper
than false positives in a coach tool. We'd rather miss a small issue
than annoy PMs with noise.
"""

import re
from typing import Any

from ..adapters import get_source
from ..config import SOURCE_NAME
from . import specs as specs_tools


# --- Heuristic 1: vague language ----------------------------------------

# Two stripes: en + zh. Each item is the term *and* a one-line "why".
# Negation-aware via word boundaries (`\b`) so "not fast" still flags
# (the term is present; PM should still quantify).
_VAGUE_TERMS_EN = {
    "fast": "Quantify (e.g., 'response within 200 ms')",
    "slow": "Quantify (e.g., 'response over 5s')",
    "quickly": "Quantify the time budget",
    "soon": "Specify the deadline",
    "easy": "Define what 'easy' means measurably (steps? clicks?)",
    "simple": "Define measurable simplicity (steps, fields, decisions)",
    "intuitive": "State the observable signal (no docs needed? 1st-time success?)",
    "user-friendly": "Replace with a measurable UX criterion",
    "user friendly": "Replace with a measurable UX criterion",
    "modern": "Replace with a concrete capability (e.g., 'supports dark mode')",
    "clean": "Define what's cleanable; usually means 'no clutter' — say which clutter",
    "beautiful": "Outside QA's scope — move to design review or drop",
    "smooth": "Quantify (e.g., 'no frame drops > 16ms')",
    "approximately": "Give a range or tolerance",
    "around": "Give a range or tolerance",
    "roughly": "Give a range or tolerance",
    "ideally": "Either it's required or it isn't — pick one",
    "reasonable": "Whose reasonable? Quantify",
    "sufficient": "Quantify the threshold",
    "adequate": "Quantify the threshold",
}

_VAGUE_TERMS_ZH = {
    "快": "量化（例如：『回應時間 < 200ms』）",
    "慢": "量化（例如：『回應時間 > 5s』）",
    "方便": "改成可觀察的條件（幾步？幾個欄位？）",
    "容易": "改成可觀察的條件",
    "簡單": "量化複雜度（步驟數、欄位數）",
    "直觀": "改成可觀察的訊號（不用看文件？首次成功率？）",
    "友善": "改成可量化的 UX 條件",
    "現代": "改成具體能力（支援深色模式？支援鍵盤操作？）",
    "順暢": "量化（例如：『無 frame drop > 16ms』）",
    "流暢": "量化（例如：『無 frame drop > 16ms』）",
    "大約": "給範圍或容忍度",
    "大概": "給範圍或容忍度",
    "差不多": "給範圍或容忍度",
    "適當": "誰覺得適當？量化",
    "合理": "誰覺得合理？量化",
    "足夠": "量化門檻",
}

# Combined for iteration, mapping each term to its suggestion.
_VAGUE_TERMS: dict[str, str] = {**_VAGUE_TERMS_EN, **_VAGUE_TERMS_ZH}


def _find_vague(text: str) -> list[dict]:
    found: list[dict] = []
    lower = text.lower()
    seen: set[str] = set()
    for term, suggestion in _VAGUE_TERMS.items():
        if term in seen:
            continue
        # Word boundary for ASCII; Chinese chars have no word boundary
        # concept — substring match is correct for them.
        if re.search(r"\W" + re.escape(term) + r"\W", " " + lower + " ") or term in lower and not term.isascii():
            seen.add(term)
            found.append(
                {
                    "issue": "vague_language",
                    "severity": "warn",
                    "evidence": term,
                    "suggestion": suggestion,
                }
            )
    return found


# --- Heuristic 2: untestable AC (describes HOW, not WHAT) ---------------

# Phrases that almost always indicate the AC is describing implementation
# detail instead of user-observable outcome.
_UNTESTABLE_PHRASES = [
    ("uses ", "Rewrite to describe what the user observes, not the internal mechanism"),
    ("calls ", "User-facing assertions, not implementation calls"),
    ("invokes ", "User-facing assertions, not implementation calls"),
    ("implements ", "AC is about behaviour, not architecture"),
    ("through the ", "Avoid naming internal pipelines; describe outcome"),
    ("via the ", "Avoid naming internal pipelines; describe outcome"),
    ("under the hood", "Move implementation notes out of AC"),
    ("internally", "Move implementation notes out of AC"),
    ("redis", "Naming infra is brittle; describe latency/availability outcomes"),
    ("kafka", "Naming infra is brittle; describe latency/availability outcomes"),
    ("the cache", "Describe observable freshness, not the cache layer"),
    ("the database", "Describe what the user sees, not where it's stored"),
    ("透過", "改寫成使用者觀察到的行為，而非內部機制"),
    ("經由", "改寫成使用者觀察到的行為，而非內部機制"),
    ("內部", "不要把架構細節塞進 AC"),
]


def _find_untestable(text: str) -> list[dict]:
    found = []
    lower = text.lower()
    for phrase, suggestion in _UNTESTABLE_PHRASES:
        if phrase in lower:
            found.append(
                {
                    "issue": "untestable_implementation_ref",
                    "severity": "error",
                    "evidence": phrase.strip(),
                    "suggestion": suggestion,
                }
            )
    return found


# --- Heuristic 3: unclear role references -------------------------------

_ROLE_RE = re.compile(
    r"\b("
    r"logged[- ]?in user"
    r"|authenticated user"
    r"|anonymous user"
    r"|guest user"
    r"|admin"
    r"|administrator"
    r"|premium user"
    r"|paid user"
    r"|free user"
    r"|trial user"
    r"|owner"
    r"|moderator"
    r")\b",
    re.IGNORECASE,
)

_ROLE_RE_ZH = re.compile(
    r"(已?登入(?:使用|用)者|管理員|訪客|付費(?:使用|用)者|免費(?:使用|用)者|擁有者|版主)"
)


def _find_role_refs(text: str) -> list[str]:
    roles = {m.group(0).lower() for m in _ROLE_RE.finditer(text)}
    roles.update(m.group(0) for m in _ROLE_RE_ZH.finditer(text))
    return sorted(roles)


def _has_precondition_section(body: str) -> bool:
    return bool(re.search(r"^\s*#{1,6}\s*(precondition|preconditions|前置條件|前提)", body, re.IGNORECASE | re.MULTILINE))


# --- Tools --------------------------------------------------------------


def analyze_spec_quality_tool(arguments: dict) -> dict[str, Any]:
    """Run heuristics on one spec (`spec_id`) or all specs in the current
    source (no spec_id). Returns per-spec findings.

    Severity: each finding tagged warn / error / info. `score` is a coarse
    0–100 number — each finding subtracts 5, clipped at 0. Useful for
    quick triage; not a real metric.
    """
    spec_id = arguments.get("spec_id")
    raw_text = arguments.get("raw_text")

    source = get_source(SOURCE_NAME)

    # Resolve spec(s) to analyze.
    if raw_text:
        targets = [("(raw_text)", raw_text, "")]
    elif spec_id:
        spec = source.fetch(str(spec_id))
        targets = [(spec.id, spec.body, spec.title)]
    else:
        summaries = source.list_specs()
        targets = []
        for s in summaries:
            try:
                spec = source.fetch(s.id)
            except Exception:
                continue
            targets.append((spec.id, spec.body, spec.title))

    results = []
    for spec_id_val, body, title in targets:
        parsed = specs_tools.parse_spec_tool({"raw_text": body})
        acs = parsed.get("acceptance_criteria", []) or []

        findings = []
        for ac in acs:
            text = ac.get("text", "")
            for f in _find_vague(text):
                findings.append({"ac_id": ac.get("id"), "ac_text": text, **f})
            for f in _find_untestable(text):
                findings.append({"ac_id": ac.get("id"), "ac_text": text, **f})

        roles = _find_role_refs(body)
        if roles and not _has_precondition_section(body):
            findings.append(
                {
                    "ac_id": None,
                    "ac_text": "",
                    "issue": "unclear_role_refs",
                    "severity": "info",
                    "evidence": ", ".join(roles),
                    "suggestion": "Add a Preconditions section defining each role (who they are, how to authenticate them in tests).",
                }
            )

        score = max(0, 100 - 5 * len(findings))
        results.append(
            {
                "spec_id": spec_id_val,
                "title": title,
                "ac_count": len(acs),
                "score": score,
                "finding_count": len(findings),
                "findings": findings,
            }
        )

    return {
        "source": SOURCE_NAME,
        "specs_analyzed": len(results),
        "total_findings": sum(r["finding_count"] for r in results),
        "results": results,
    }


# --- propose_spec_improvements -----------------------------------------


def propose_spec_improvements_tool(arguments: dict) -> dict[str, Any]:
    """Take the output of analyze_spec_quality (or run it inline) and
    produce a markdown coach plan that PMs / spec authors can act on.
    """
    analysis = arguments.get("analysis")
    if not analysis:
        analysis = analyze_spec_quality_tool({k: v for k, v in arguments.items() if k != "analysis"})

    md_lines = ["# Spec quality coach", ""]
    total = analysis.get("total_findings", 0)
    md_lines.append(f"**{total} finding(s) across {analysis.get('specs_analyzed', 0)} spec(s).**")
    if total == 0:
        md_lines += ["", "🟢 No issues caught by current heuristics. Note this checks for **vague language**, **untestable implementation refs**, and **unclear role refs** — semantic correctness still needs human review."]
        return {"markdown": "\n".join(md_lines), "actions": []}

    actions: list[dict] = []
    for spec_result in analysis.get("results", []):
        if spec_result["finding_count"] == 0:
            continue
        md_lines.append("")
        md_lines.append(f"## `{spec_result['spec_id']}` — {spec_result.get('title') or ''}")
        md_lines.append(f"_score: {spec_result['score']}/100 · findings: {spec_result['finding_count']}_")
        md_lines.append("")

        grouped: dict[str, list[dict]] = {}
        for f in spec_result["findings"]:
            grouped.setdefault(f["issue"], []).append(f)

        for issue, items in grouped.items():
            severity = items[0].get("severity", "warn")
            badge = {"error": "🔴", "warn": "🟡", "info": "🔵"}.get(severity, "•")
            human_name = {
                "vague_language": "Vague language",
                "untestable_implementation_ref": "Untestable / implementation-detail AC",
                "unclear_role_refs": "Unclear role references",
            }.get(issue, issue)
            md_lines.append(f"### {badge} {human_name}  *(×{len(items)})*")
            md_lines.append("")
            for f in items:
                ac_label = f"`{f['ac_id']}`" if f.get("ac_id") else "_(spec-level)_"
                md_lines.append(f"- {ac_label}: evidence — `{f['evidence']}`")
                md_lines.append(f"  - **Suggestion:** {f['suggestion']}")
                if f.get("ac_text"):
                    md_lines.append(f"  - **Source AC:** > {f['ac_text']}")
            md_lines.append("")

            actions.append(
                {
                    "spec_id": spec_result["spec_id"],
                    "issue": issue,
                    "count": len(items),
                    "severity": severity,
                }
            )

    return {
        "markdown": "\n".join(md_lines),
        "actions": actions,
    }
