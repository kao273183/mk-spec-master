"""History archive + trend tools for v0.4 self-reinforcement.

Every get_optimization_plan call writes a snapshot here. Other tools
read the archive to compute trend deltas and detect chronic problems
(specs that show up in drift or quality findings repeatedly).

Storage: <HISTORY_DIR>/<UTC-ISO-timestamp>.json — one file per snapshot.
Append-only. Old snapshots can be safely deleted by the user; tools
degrade gracefully (just less trend granularity).
"""

import datetime as _dt
import json
from pathlib import Path
from typing import Any

from .. import config


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _now_dt() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def archive_snapshot(snapshot: dict) -> str:
    """Write one snapshot JSON. Returns the path. Called from
    get_optimization_plan_tool. Failures are swallowed (we don't want
    history persistence to break the live coach output)."""
    try:
        config.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        stamped = dict(snapshot)
        stamped["timestamp"] = _now_iso()
        path = config.HISTORY_DIR / f"{stamped['timestamp']}.json"
        path.write_text(json.dumps(stamped, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return str(path)
    except (OSError, TypeError):
        return ""


def _read_snapshots(limit: int | None = None) -> list[dict]:
    """Return snapshots in chronological order (oldest first). Reads the
    directory listing; tolerates missing dir + bad files."""
    if not config.HISTORY_DIR.exists():
        return []
    files = sorted(config.HISTORY_DIR.glob("*.json"))
    if limit:
        files = files[-limit:]
    out: list[dict] = []
    for f in files:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def _delta(current: float | int, previous: float | int) -> str:
    diff = current - previous
    if diff > 0:
        return f"+{diff}"
    if diff < 0:
        return f"{diff}"
    return "±0"


def get_spec_history_tool(arguments: dict) -> dict[str, Any]:
    """Return the last N snapshots + trend deltas (current vs ~7 days ago
    and ~30 days ago when those windows have data).

    Args:
        limit: int, default 10 — how many of the latest snapshots to return.
    """
    limit = int(arguments.get("limit", 10))
    snapshots = _read_snapshots()

    if not snapshots:
        return {
            "snapshots_total": 0,
            "snapshots": [],
            "trend": None,
            "markdown": "# Spec history\n\n_No snapshots yet — run `get_optimization_plan` to start tracking._",
        }

    recent = snapshots[-limit:]
    latest = snapshots[-1]
    now = _now_dt()

    def _pick(days_ago: int) -> dict | None:
        target = now - _dt.timedelta(days=days_ago)
        best = None
        best_gap = None
        for snap in snapshots:
            try:
                ts = _dt.datetime.strptime(snap["timestamp"], "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=_dt.timezone.utc)
            except (KeyError, ValueError):
                continue
            gap = abs((ts - target).total_seconds())
            if best is None or gap < best_gap:
                best = snap
                best_gap = gap
        # Only return if best is within 1.5x the target window (avoid using
        # day-0 snapshot as the "30 days ago" baseline).
        if best is None or best_gap > days_ago * 86400 * 1.5:
            return None
        return best

    baseline_7d = _pick(7)
    baseline_30d = _pick(30)

    def _row(field: str, label: str) -> dict:
        return {
            "field": field,
            "label": label,
            "current": latest.get(field, 0),
            "vs_7d": _delta(latest.get(field, 0), baseline_7d[field]) if baseline_7d and field in baseline_7d else "—",
            "vs_30d": _delta(latest.get(field, 0), baseline_30d[field]) if baseline_30d and field in baseline_30d else "—",
        }

    trend = [
        _row("specs_total", "Specs tracked"),
        _row("untested_count", "Untested specs"),
        _row("quality_findings", "Quality findings"),
        _row("drifted_count", "Drifted specs"),
        _row("stranded_count", "Stranded specs"),
        _row("unknown_count", "Specs w/o ac_hash"),
    ]

    md = [
        "# Spec history",
        "",
        f"- Snapshots archived: {len(snapshots)}",
        f"- Latest snapshot: {latest.get('timestamp', '?')}",
        "",
        "| Metric | Current | vs 7d | vs 30d |",
        "|---|---:|---:|---:|",
    ]
    for r in trend:
        md.append(f"| {r['label']} | {r['current']} | {r['vs_7d']} | {r['vs_30d']} |")
    md.append("")
    md.append(f"_Lower is better for untested / findings / drifted / stranded / unknown. Increases are red flags._")

    return {
        "snapshots_total": len(snapshots),
        "snapshots": recent,
        "trend": trend,
        "markdown": "\n".join(md),
    }


def get_drift_signature_tool(arguments: dict) -> dict[str, Any]:
    """Scan history for chronic problems: same spec_id repeatedly showing
    up in drifted / unknown / low-quality buckets.

    Threshold defaults: appears in >= 3 of the last 5 snapshots → chronic.

    Args:
        window: int, default 5 — how many recent snapshots to scan.
        threshold: int, default 3 — minimum recurrence to flag as chronic.
    """
    window = int(arguments.get("window", 5))
    threshold = int(arguments.get("threshold", 3))

    snapshots = _read_snapshots(limit=window)
    if len(snapshots) < threshold:
        return {
            "ready": False,
            "snapshots_available": len(snapshots),
            "snapshots_needed": threshold,
            "chronic": [],
            "markdown": (
                "# Drift signature\n\n"
                f"_Need at least {threshold} snapshots; have {len(snapshots)}. "
                f"Run `get_optimization_plan` over time to build history._"
            ),
        }

    drift_counts: dict[str, int] = {}
    unknown_counts: dict[str, int] = {}
    quality_counts: dict[str, int] = {}

    for snap in snapshots:
        for d in snap.get("drifted", []) or []:
            sid = d.get("spec_id")
            if sid:
                drift_counts[sid] = drift_counts.get(sid, 0) + 1
        for u in snap.get("unknown", []) or []:
            sid = u.get("spec_id")
            if sid:
                unknown_counts[sid] = unknown_counts.get(sid, 0) + 1
        for q in snap.get("quality", []) or []:
            sid = q.get("spec_id")
            if sid:
                quality_counts[sid] = quality_counts.get(sid, 0) + 1

    chronic = []
    for sid, count in drift_counts.items():
        if count >= threshold:
            chronic.append({"spec_id": sid, "kind": "unstable", "appearances": count, "window": len(snapshots),
                            "reason": "Spec keeps changing after being linked — PM may be iterating without resetting downstream tests."})
    for sid, count in quality_counts.items():
        if count >= threshold:
            chronic.append({"spec_id": sid, "kind": "chronic_low_quality", "appearances": count, "window": len(snapshots),
                            "reason": "Spec is repeatedly flagged for vague language / implementation-leak / unclear roles."})
    for sid, count in unknown_counts.items():
        if count >= threshold:
            chronic.append({"spec_id": sid, "kind": "chronic_unhashed", "appearances": count, "window": len(snapshots),
                            "reason": "Linked tests never recorded an ac_hash — re-link with parse_spec._meta.ac_hash to enable drift detection."})

    chronic.sort(key=lambda r: (-r["appearances"], r["spec_id"]))

    md = ["# Drift signature", ""]
    md.append(f"- Window: last {len(snapshots)} snapshots")
    md.append(f"- Threshold: ≥ {threshold} appearances = chronic")
    md.append(f"- Chronic specs flagged: {len(chronic)}")
    md.append("")
    if not chronic:
        md.append("🟢 No chronic patterns detected. Keep an eye on the next few snapshots.")
    else:
        kind_label = {
            "unstable": "🔴 Unstable (repeatedly drifting)",
            "chronic_low_quality": "🟡 Chronically low quality",
            "chronic_unhashed": "⚪ Chronically without ac_hash",
        }
        last_kind = None
        for c in chronic:
            if c["kind"] != last_kind:
                md.append("")
                md.append(f"## {kind_label.get(c['kind'], c['kind'])}")
                last_kind = c["kind"]
            md.append(f"- `{c['spec_id']}` — appeared {c['appearances']}/{c['window']} snapshots · {c['reason']}")

    return {
        "ready": True,
        "snapshots_scanned": len(snapshots),
        "threshold": threshold,
        "chronic": chronic,
        "markdown": "\n".join(md),
    }
