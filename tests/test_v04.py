"""Tests for v0.4 self-reinforcement: history archive, trend analysis,
drift signature detection, telemetry log + aggregator."""

import datetime as _dt
import json
import time

import pytest


def _isolate(tmp_path, monkeypatch):
    from mk_spec_master import config
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path / ".mk-spec-master")
    monkeypatch.setattr(config, "INDEX_PATH", tmp_path / ".mk-spec-master" / "index.json")
    monkeypatch.setattr(config, "HISTORY_DIR", tmp_path / ".mk-spec-master" / "history")
    monkeypatch.setattr(config, "TELEMETRY_PATH", tmp_path / ".mk-spec-master" / "telemetry.jsonl")


# ---------- history archive on optimization plan -----------------------


def test_optimization_plan_archives_snapshot(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from mk_spec_master.tools.optimization import get_optimization_plan_tool

    get_optimization_plan_tool({})

    history_dir = tmp_path / ".mk-spec-master" / "history"
    assert history_dir.exists()
    files = list(history_dir.glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert "timestamp" in payload
    assert "specs_total" in payload


def test_optimization_plan_skip_archive_flag(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from mk_spec_master.tools.optimization import get_optimization_plan_tool

    get_optimization_plan_tool({"skip_archive": True})

    history_dir = tmp_path / ".mk-spec-master" / "history"
    assert not history_dir.exists() or not list(history_dir.glob("*.json"))


# ---------- get_spec_history ------------------------------------------


def test_get_spec_history_empty_state(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from mk_spec_master.tools.history import get_spec_history_tool

    result = get_spec_history_tool({})
    assert result["snapshots_total"] == 0
    assert "No snapshots yet" in result["markdown"]


def test_get_spec_history_returns_recent_with_trend(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    history_dir = tmp_path / ".mk-spec-master" / "history"
    history_dir.mkdir(parents=True)

    # Plant 3 snapshots: 30 days ago, 7 days ago, now. Quality findings
    # shrinking over time (15 → 8 → 3) — should show clear improvement.
    now = _dt.datetime.now(_dt.timezone.utc)
    for offset_days, findings, untested in [(30, 15, 10), (7, 8, 5), (0, 3, 2)]:
        ts = (now - _dt.timedelta(days=offset_days)).strftime("%Y-%m-%dT%H-%M-%SZ")
        (history_dir / f"{ts}.json").write_text(json.dumps({
            "timestamp": ts,
            "specs_total": 20,
            "untested_count": untested,
            "quality_findings": findings,
            "drifted_count": 0,
            "stranded_count": 0,
            "unknown_count": 0,
        }))

    from mk_spec_master.tools.history import get_spec_history_tool
    result = get_spec_history_tool({})

    assert result["snapshots_total"] == 3
    findings_row = next(r for r in result["trend"] if r["field"] == "quality_findings")
    assert findings_row["current"] == 3
    assert findings_row["vs_7d"] == "-5"   # 3 - 8 = -5
    assert findings_row["vs_30d"] == "-12" # 3 - 15 = -12


# ---------- drift_signature -------------------------------------------


def test_drift_signature_not_ready_when_too_few_snapshots(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from mk_spec_master.tools.history import get_drift_signature_tool

    result = get_drift_signature_tool({})
    assert result["ready"] is False
    assert "Need at least" in result["markdown"]


def test_drift_signature_flags_chronic_unstable_spec(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    history_dir = tmp_path / ".mk-spec-master" / "history"
    history_dir.mkdir(parents=True)

    # 5 snapshots; LIN-CHRONIC appears in drifted bucket in 4 of them.
    for i in range(5):
        ts = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=4 - i)).strftime("%Y-%m-%dT%H-%M-%SZ")
        drifted = [{"spec_id": "LIN-CHRONIC"}] if i != 2 else []
        (history_dir / f"{ts}.json").write_text(json.dumps({
            "timestamp": ts,
            "drifted": drifted,
            "unknown": [],
            "quality": [],
        }))

    from mk_spec_master.tools.history import get_drift_signature_tool
    result = get_drift_signature_tool({"window": 5, "threshold": 3})

    assert result["ready"] is True
    assert any(c["spec_id"] == "LIN-CHRONIC" and c["kind"] == "unstable" for c in result["chronic"])


def test_drift_signature_skips_one_off_specs(tmp_path, monkeypatch):
    """A spec appearing once should not be flagged."""
    _isolate(tmp_path, monkeypatch)
    history_dir = tmp_path / ".mk-spec-master" / "history"
    history_dir.mkdir(parents=True)

    for i in range(5):
        ts = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=4 - i)).strftime("%Y-%m-%dT%H-%M-%SZ")
        drifted = [{"spec_id": "LIN-ONEOFF"}] if i == 0 else []
        (history_dir / f"{ts}.json").write_text(json.dumps({
            "timestamp": ts,
            "drifted": drifted,
            "unknown": [],
            "quality": [],
        }))

    from mk_spec_master.tools.history import get_drift_signature_tool
    result = get_drift_signature_tool({"window": 5, "threshold": 3})

    assert all(c["spec_id"] != "LIN-ONEOFF" for c in result["chronic"])


# ---------- telemetry --------------------------------------------------


def test_telemetry_log_appends_jsonl(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from mk_spec_master.tools.telemetry import log_tool_call

    log_tool_call("list_specs", 42, None)
    log_tool_call("fetch_spec", 100, "ValueError: not found")
    log_tool_call("list_specs", 35, None)

    lines = (tmp_path / ".mk-spec-master" / "telemetry.jsonl").read_text().splitlines()
    assert len(lines) == 3
    records = [json.loads(line) for line in lines]
    assert records[0]["tool"] == "list_specs"
    assert records[1]["ok"] is False
    assert records[1]["error"].startswith("ValueError")


def test_get_telemetry_aggregates_by_tool(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from mk_spec_master.tools.telemetry import log_tool_call, get_telemetry_tool

    for _ in range(5):
        log_tool_call("list_specs", 30, None)
    log_tool_call("fetch_spec", 200, "TimeoutError: slow")
    log_tool_call("fetch_spec", 50, None)

    result = get_telemetry_tool({"include_inactive": False})
    by_tool = {r["tool"]: r for r in result["tools"]}

    assert by_tool["list_specs"]["calls"] == 5
    assert by_tool["list_specs"]["errors"] == 0
    assert by_tool["fetch_spec"]["calls"] == 2
    assert by_tool["fetch_spec"]["errors"] == 1
    assert by_tool["fetch_spec"]["error_rate_pct"] == 50.0


def test_get_telemetry_window_filters_old_records(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from mk_spec_master import config

    # Hand-write an old + new record.
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    old_ts = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    config.TELEMETRY_PATH.write_text("\n".join([
        json.dumps({"timestamp": old_ts, "tool": "old_tool", "ok": True, "duration_ms": 10}),
        json.dumps({"timestamp": new_ts, "tool": "new_tool", "ok": True, "duration_ms": 10}),
    ]) + "\n")

    from mk_spec_master.tools.telemetry import get_telemetry_tool
    result = get_telemetry_tool({"days": 30, "include_inactive": False})

    tools_seen = {r["tool"] for r in result["tools"]}
    assert "new_tool" in tools_seen
    assert "old_tool" not in tools_seen


def test_get_telemetry_lists_inactive_tools(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from mk_spec_master.tools.telemetry import log_tool_call, get_telemetry_tool

    log_tool_call("list_specs", 20, None)

    result = get_telemetry_tool({"include_inactive": True})
    assert "fetch_spec" in result["inactive"]  # declared but never logged
    assert "list_specs" not in result["inactive"]


def test_telemetry_timer_records_duration_and_error(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    from mk_spec_master.tools.telemetry import _Timer
    from mk_spec_master import config

    with _Timer("happy_tool"):
        time.sleep(0.005)  # 5ms

    with pytest.raises(ValueError):
        with _Timer("sad_tool"):
            raise ValueError("boom")

    lines = config.TELEMETRY_PATH.read_text().splitlines()
    records = [json.loads(line) for line in lines]
    happy = next(r for r in records if r["tool"] == "happy_tool")
    sad = next(r for r in records if r["tool"] == "sad_tool")
    assert happy["ok"] is True
    assert happy["duration_ms"] >= 5
    assert sad["ok"] is False
    assert "ValueError" in sad["error"]
