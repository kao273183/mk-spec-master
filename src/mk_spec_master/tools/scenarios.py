"""Scenario generation + handoff markdown for mk-qa-master.

v0.1 is intentionally heuristic — the AI client refines the output. The
goal here is "structured enough to feed straight into mk-qa-master's
generate_test(business_context=...)", not "publish-ready Gherkin".
"""

import re
from typing import Any

from . import specs as specs_tools

_ERROR_HINTS = (
    "invalid", "expired", "not recognized", "not found", "denied", "fail",
    "error", "rejected", "blocked", "forbidden", "unauthorized",
    "錯誤", "失敗", "拒絕", "無效", "過期",
)
_EDGE_HINTS = (
    "empty", "zero", "max", "min", "limit", "boundary", "overflow",
    "edge", "first time", "concurrent", "race",
    "邊界", "極限", "空", "上限", "下限",
)

# Loose "user does X → result Y" splitter. Supports → / -> / "such that" /
# 「則」 / commas. If the heuristic misses, we fall back to a single Then.
_GWT_SPLITTERS = [r"→", r"->", r"such that", r"results? in", r"shows?", r"則", r"，然後", r", then "]
_GWT_SPLIT_RE = re.compile("|".join(_GWT_SPLITTERS), re.IGNORECASE)


_NEGATION_PREFIXES = ("non-", "not ", "no ", "without ", "未", "沒")


def _has_signal(text: str, hints: tuple[str, ...]) -> bool:
    """True if any hint appears in `text` *not* preceded by a negation
    word. Catches the 'non-expired' false-positive that a naive substring
    check would flag."""
    lower = text.lower()
    for hint in hints:
        idx = 0
        while True:
            pos = lower.find(hint, idx)
            if pos == -1:
                break
            preceding = lower[max(0, pos - 10):pos]
            if any(neg in preceding for neg in _NEGATION_PREFIXES):
                idx = pos + len(hint)
                continue
            return True
    return False


def _classify(text: str) -> str:
    if _has_signal(text, _ERROR_HINTS):
        return "error"
    if _has_signal(text, _EDGE_HINTS):
        return "edge"
    return "happy"


def _split_gwt(text: str) -> tuple[str, str, str]:
    """Best-effort Given/When/Then split. Returns ('', when, then) when the
    text is short; the AI client typically fills Given from context."""
    parts = _GWT_SPLIT_RE.split(text, maxsplit=1)
    if len(parts) == 2:
        return "", parts[0].strip(), parts[1].strip()
    return "", "", text.strip()


def _scenario_title(ac_text: str, kind: str) -> str:
    """First clause up to 60 chars + kind tag. Good enough for test name; AI
    client can rename if desired."""
    first = re.split(r"[.。→\-—]", ac_text, maxsplit=1)[0].strip()
    if len(first) > 60:
        first = first[:57] + "..."
    return first or f"{kind} scenario"


def extract_scenarios_tool(arguments: dict) -> dict[str, Any]:
    """Input: acceptance_criteria list of {id, text} (from parse_spec).
    Output: scenarios with title / kind / given / when / then."""
    acs = arguments.get("acceptance_criteria") or []
    if not isinstance(acs, list):
        return {"error": "acceptance_criteria must be a list of {id, text} dicts"}

    scenarios = []
    for ac in acs:
        if not isinstance(ac, dict):
            continue
        ac_id = str(ac.get("id") or f"ac-{len(scenarios) + 1}")
        text = str(ac.get("text") or "").strip()
        if not text:
            continue

        kind = _classify(text)
        given, when, then = _split_gwt(text)

        scenarios.append(
            {
                "id": f"scenario-{len(scenarios) + 1}",
                "ac_id": ac_id,
                "title": _scenario_title(text, kind),
                "kind": kind,
                "given": given,
                "when": when,
                "then": then or text,
            }
        )

    return {
        "count": len(scenarios),
        "scenarios": scenarios,
    }


def generate_test_plan_tool(arguments: dict) -> dict[str, Any]:
    """Produce a markdown plan ready for mk-qa-master.generate_test handoff.

    The 'business_context' field of mk-qa-master.generate_test accepts free
    text — we emit one block per scenario that an AI client can hand over
    verbatim per call.
    """
    spec_id = arguments.get("spec_id")
    if not spec_id:
        return {"error": "spec_id is required"}

    target_runner = arguments.get("target_runner", "pytest")

    parsed = specs_tools.parse_spec_tool({"spec_id": spec_id})
    if "error" in parsed:
        return parsed

    extracted = extract_scenarios_tool(
        {"acceptance_criteria": parsed.get("acceptance_criteria", [])}
    )

    scenarios = extracted.get("scenarios", [])

    md = [
        f"# Test plan — {parsed.get('title') or spec_id}",
        "",
        f"- spec id: `{spec_id}`",
        f"- target runner: `{target_runner}`",
        f"- scenarios: {len(scenarios)}",
        "",
        "## Scenarios",
        "",
    ]
    for sc in scenarios:
        md.append(f"### {sc['title']}  *(kind: {sc['kind']}, links: {sc['ac_id']})*")
        if sc["given"]:
            md.append(f"- **Given** {sc['given']}")
        if sc["when"]:
            md.append(f"- **When** {sc['when']}")
        md.append(f"- **Then** {sc['then']}")
        md.append("")
        md.append("**Handoff to mk-qa-master.generate_test:**")
        md.append("")
        md.append("```")
        md.append(f"business_context: |")
        md.append(f"  Spec: {spec_id} — {parsed.get('title') or ''}")
        md.append(f"  Scenario ({sc['kind']}): {sc['title']}")
        if sc["given"]:
            md.append(f"  Given: {sc['given']}")
        if sc["when"]:
            md.append(f"  When: {sc['when']}")
        md.append(f"  Then: {sc['then']}")
        md.append("```")
        md.append("")

    return {
        "spec_id": spec_id,
        "target_runner": target_runner,
        "scenario_count": len(scenarios),
        "markdown": "\n".join(md),
        "scenarios": scenarios,
    }
