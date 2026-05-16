"""Tool-usage telemetry for v0.4 self-reinforcement.

Every call_tool dispatch in server.py writes one JSONL line. get_telemetry
aggregates by tool to surface usage / error patterns: which tools get
called often, which fail often, which never get called.

Storage: <TELEMETRY_PATH> — append-only JSONL. One line = one tool call.
Schema: {timestamp, tool, ok, duration_ms, error?}.

Privacy: argument values are NEVER logged. Only the tool name + outcome.
"""

import datetime as _dt
import json
import time
from typing import Any

from .. import config


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_tool_call(tool: str, duration_ms: int, error: str | None = None) -> None:
    """Append a single record. Swallows storage errors so telemetry
    can never crash a tool call."""
    try:
        config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": _now_iso(),
            "tool": tool,
            "ok": error is None,
            "duration_ms": duration_ms,
        }
        if error:
            record["error"] = error[:200]  # bound the error string
        with config.TELEMETRY_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


class _Timer:
    """Tiny context manager so server.py can wrap dispatch cleanly."""

    def __init__(self, tool: str):
        self.tool = tool
        self.error: str | None = None
        self._start = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        duration_ms = int((time.perf_counter() - self._start) * 1000)
        if exc is not None:
            self.error = f"{exc_type.__name__}: {exc}"
        log_tool_call(self.tool, duration_ms, self.error)
        return False  # never swallow exceptions


def get_telemetry_tool(arguments: dict) -> dict[str, Any]:
    """Aggregate the telemetry log by tool. Surfaces:
    - call counts (most / least used)
    - error rates (which tools fail)
    - duration p50 / p95 (perf hot spots)
    - inactive tools (declared but never called)

    Args:
        days: int, default 30 — only count records from the last N days.
        include_inactive: bool, default True — list tools with 0 calls.
    """
    days = int(arguments.get("days", 30))
    include_inactive = bool(arguments.get("include_inactive", True))

    if not config.TELEMETRY_PATH.exists():
        return {
            "records_total": 0,
            "tools": [],
            "markdown": "# Telemetry\n\n_No tool calls recorded yet._",
        }

    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)
    records: list[dict] = []
    try:
        for line in config.TELEMETRY_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                ts = _dt.datetime.strptime(rec["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
            except (KeyError, ValueError):
                continue
            if ts >= cutoff:
                records.append(rec)
    except OSError:
        return {"records_total": 0, "tools": [], "markdown": "# Telemetry\n\n_Telemetry log unreadable._"}

    by_tool: dict[str, dict[str, Any]] = {}
    for r in records:
        t = r.get("tool", "?")
        bucket = by_tool.setdefault(t, {"calls": 0, "ok": 0, "errors": 0, "durations": []})
        bucket["calls"] += 1
        if r.get("ok"):
            bucket["ok"] += 1
        else:
            bucket["errors"] += 1
        bucket["durations"].append(int(r.get("duration_ms", 0)))

    rows = []
    for tool, b in by_tool.items():
        durations = sorted(b["durations"])
        n = len(durations)
        p50 = durations[n // 2] if n else 0
        p95 = durations[min(n - 1, int(n * 0.95))] if n else 0
        error_rate = b["errors"] / b["calls"] if b["calls"] else 0.0
        rows.append(
            {
                "tool": tool,
                "calls": b["calls"],
                "ok": b["ok"],
                "errors": b["errors"],
                "error_rate_pct": round(error_rate * 100, 1),
                "p50_ms": p50,
                "p95_ms": p95,
            }
        )

    rows.sort(key=lambda r: -r["calls"])

    # Inactive tools — declared in DISPATCH but absent from records.
    inactive: list[str] = []
    if include_inactive:
        try:
            # Local import to avoid cycle; server defines the canonical list.
            from ..server import _DISPATCH
            seen = set(by_tool)
            inactive = sorted(t for t in _DISPATCH if t not in seen)
        except Exception:
            inactive = []

    md = [
        "# Telemetry",
        "",
        f"- Window: last {days} day(s)",
        f"- Total tool calls: {len(records)}",
        f"- Distinct tools called: {len(by_tool)}",
        "",
        "| Tool | Calls | Errors | Err rate | p50 ms | p95 ms |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        md.append(
            f"| `{r['tool']}` | {r['calls']} | {r['errors']} | {r['error_rate_pct']}% | {r['p50_ms']} | {r['p95_ms']} |"
        )

    if include_inactive and inactive:
        md.append("")
        md.append("## Inactive tools (declared but never called in window)")
        md.append("")
        for t in inactive:
            md.append(f"- `{t}`")

    return {
        "records_total": len(records),
        "window_days": days,
        "tools": rows,
        "inactive": inactive,
        "markdown": "\n".join(md),
    }
