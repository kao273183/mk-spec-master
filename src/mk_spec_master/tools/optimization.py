"""get_optimization_plan — three-layer coach output that integrates
coverage / quality / drift signals into one prioritized action plan.

Mirrors mk-qa-master's get_optimization_plan in spirit: a single tool
that doesn't add new data, just *integrates and ranks* what the other
tools already surface. PMs / QA leads can paste this directly into a
sprint planning doc.

Layer 1 — Coverage gaps     (data from get_coverage_matrix)
Layer 2 — Spec quality      (data from analyze_spec_quality)
Layer 3 — Process drift     (data from get_drift_report)
"""

from typing import Any

from . import coverage as coverage_tools
from . import quality as quality_tools


def _badge(severity: str) -> str:
    return {"error": "🔴", "warn": "🟡", "info": "🔵"}.get(severity, "•")


def get_optimization_plan_tool(arguments: dict) -> dict[str, Any]:
    include_coverage = bool(arguments.get("include_coverage", True))
    include_quality = bool(arguments.get("include_quality", True))
    include_drift = bool(arguments.get("include_drift", True))
    top_n = int(arguments.get("top_n", 10))

    coverage_data: dict = {}
    quality_data: dict = {}
    drift_data: dict = {}

    if include_coverage:
        coverage_data = coverage_tools.get_coverage_matrix_tool({"min_tests": 0})

    if include_quality:
        try:
            quality_data = quality_tools.analyze_spec_quality_tool({})
        except Exception as exc:
            quality_data = {"error": str(exc)}

    if include_drift:
        try:
            drift_data = coverage_tools.get_drift_report_tool({})
        except Exception as exc:
            drift_data = {"error": str(exc)}

    # ----- Layer 1: coverage gaps -----
    untested = [row for row in (coverage_data.get("rows") or []) if row.get("tests_count") == 0][:top_n]
    low_coverage = [row for row in (coverage_data.get("rows") or []) if 0 < row.get("tests_count", 0) <= 1][:top_n]

    # ----- Layer 2: spec quality -----
    quality_results = quality_data.get("results") or []
    sorted_quality = sorted(
        (r for r in quality_results if r.get("finding_count", 0) > 0),
        key=lambda r: (
            -sum(1 for f in r.get("findings", []) if f.get("severity") == "error"),
            -r.get("finding_count", 0),
            r.get("score", 100),
        ),
    )[:top_n]

    # ----- Layer 3: process drift -----
    drifted = (drift_data.get("drifted") or [])[:top_n]
    stranded = (drift_data.get("stranded") or [])[:top_n]
    unknown_count = drift_data.get("unknown_count", 0)

    # ----- markdown plan -----
    md: list[str] = ["# Optimization plan", ""]

    if include_coverage:
        md.append(
            f"_Coverage matrix: {coverage_data.get('specs_total', 0)} spec(s) tracked, "
            f"{coverage_data.get('specs_untested', 0)} untested._"
        )
    if include_quality:
        md.append(
            f"_Spec quality: {quality_data.get('specs_analyzed', 0)} spec(s) analyzed, "
            f"{quality_data.get('total_findings', 0)} finding(s)._"
        )
    if include_drift:
        md.append(
            f"_Drift: {drift_data.get('drifted_count', 0)} drifted, "
            f"{drift_data.get('stranded_count', 0)} stranded, "
            f"{drift_data.get('unknown_count', 0)} without ac_hash._"
        )
    md.append("")

    if include_coverage:
        md.append("## 🔴 Layer 1 — Coverage gaps")
        md.append("")
        if untested:
            md.append("**Specs with zero tests** (ranked first — every business risk lives here):")
            md.append("")
            for row in untested:
                md.append(f"- `{row['spec_id']}` — {row.get('title') or '_(no metadata)_'}")
            md.append("")
        if low_coverage:
            md.append("**Specs with only one linked test** (typically happy-path only — consider an edge/error scenario):")
            md.append("")
            for row in low_coverage:
                md.append(f"- `{row['spec_id']}` — {row.get('title') or ''}")
            md.append("")
        if not untested and not low_coverage:
            md.append("🟢 No coverage gaps at the visible threshold.")
            md.append("")

    if include_quality:
        md.append("## 🟡 Layer 2 — Spec quality")
        md.append("")
        if quality_data.get("error"):
            md.append(f"_Skipped: {quality_data['error']}_")
            md.append("")
        elif sorted_quality:
            for r in sorted_quality:
                md.append(f"### `{r['spec_id']}` — {r.get('title') or ''}  *(score: {r['score']}/100, findings: {r['finding_count']})*")
                # Take up to 3 most-severe findings per spec
                findings = sorted(r.get("findings", []), key=lambda f: {"error": 0, "warn": 1, "info": 2}.get(f.get("severity"), 3))[:3]
                for f in findings:
                    badge = _badge(f.get("severity", "warn"))
                    ac_ref = f"`{f['ac_id']}`: " if f.get("ac_id") else ""
                    md.append(f"- {badge} {ac_ref}{f.get('suggestion', '')}  *(evidence: `{f.get('evidence', '')}`)*")
                md.append("")
        else:
            md.append("🟢 No quality issues caught by current heuristics.")
            md.append("")

    if include_drift:
        md.append("## 🔵 Layer 3 — Process drift")
        md.append("")
        if drift_data.get("error"):
            md.append(f"_Skipped: {drift_data['error']}_")
            md.append("")
        else:
            if drifted:
                md.append("**Drifted** (spec changed since link — review affected tests):")
                md.append("")
                for d in drifted:
                    md.append(f"- `{d['spec_id']}` — {d.get('title') or ''} · {len(d.get('linked_test_node_ids') or [])} test(s) potentially stale")
                md.append("")
            if stranded:
                md.append("**Stranded** (spec_id can no longer be fetched — clean the index or fix the source):")
                md.append("")
                for s in stranded:
                    md.append(f"- `{s['spec_id']}` — {s.get('reason', '')}")
                md.append("")
            if unknown_count:
                md.append(f"_{unknown_count} spec(s) have no `ac_hash` stored. Re-link with the `ac_hash` argument to enable drift detection going forward._")
                md.append("")
            if not drifted and not stranded:
                md.append("🟢 No active drift signal.")
                md.append("")

    # Counters for the top-level structured response.
    return {
        "specs_total": coverage_data.get("specs_total", 0),
        "untested_count": len(untested),
        "low_coverage_count": len(low_coverage),
        "quality_findings": quality_data.get("total_findings", 0),
        "drifted_count": drift_data.get("drifted_count", 0),
        "stranded_count": drift_data.get("stranded_count", 0),
        "unknown_count": unknown_count,
        "untested": untested,
        "low_coverage": low_coverage,
        "quality": sorted_quality,
        "drifted": drifted,
        "stranded": stranded,
        "markdown": "\n".join(md),
    }
