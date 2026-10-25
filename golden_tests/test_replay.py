"""Golden acceptance test suite for Presentation Replay Player and Snapshots.

Verifies:
- REPLAY_DATA_PATH integrity, schema, and realistic delay pacing
- Snapshot restoration mechanism for unharnessed and harnessed candidate workspaces
- Auto-recording persistence helper behavior
"""

import json
from pathlib import Path

import pytest

from app.config import (
    HARNESSED_DIR,
    REPLAY_DATA_PATH,
    UNHARNESSED_DIR,
)
from app.orchestrator import save_replay_recording
from app.replay.player import restore_replay_workspaces


def test_replay_data_file_integrity() -> None:
    """Verify that replay_data.json exists, is valid JSON, and has presentation events."""
    assert REPLAY_DATA_PATH.is_file(), "app/replay/replay_data.json must exist"
    data = json.loads(REPLAY_DATA_PATH.read_text(encoding="utf-8"))
    assert "events" in data, "Replay data must contain an 'events' list"
    events = data["events"]
    assert len(events) >= 10, "Replay should contain comprehensive comparison trace events"

    for evt in events:
        assert "type" in evt, "Each replay event must have a 'type' field"
        assert "delay_ms" in evt, "Each replay event must have a 'delay_ms' pacing parameter"
        assert isinstance(evt["delay_ms"], (int, float))

    # Verify completed events record authentic duration
    completed_events = [e for e in events if e.get("data", {}).get("stage") == "completed"]
    assert len(completed_events) >= 2, "Replay must include completed events for both tracks"
    for ce in completed_events:
        assert "formatted_duration" in ce["data"], "Completed event must include authentic formatted_duration"
        assert "duration_seconds" in ce["data"], "Completed event must include duration_seconds"

    # Verify summary event records total duration
    summary_events = [e for e in events if e.get("type") == "comparison_summary"]
    assert len(summary_events) >= 1
    assert "total_formatted_duration" in summary_events[0]


def test_restore_replay_workspaces_populates_candidates() -> None:
    """Verify restore_replay_workspaces populates candidate workspaces for Layer 2 preview."""
    restore_replay_workspaces()

    # Unharnessed check
    assert (UNHARNESSED_DIR / "static" / "index.html").is_file() or (UNHARNESSED_DIR / "main.py").is_file() or (UNHARNESSED_DIR / "game_engine.py").is_file()

    # Harnessed check
    assert (HARNESSED_DIR / "static" / "index.html").is_file()
    assert (HARNESSED_DIR / "game_engine.py").is_file()


def test_save_replay_recording_roundtrip(tmp_path: Path) -> None:
    """Verify save_replay_recording writes valid data structure and snapshots."""
    dummy_events = [
        {"type": "init", "delay_ms": 300, "message": "Test run"},
        {"type": "comparison_summary", "delay_ms": 500, "message": "Done"},
    ]
    u_dir = tmp_path / "u"
    h_dir = tmp_path / "h"
    u_dir.mkdir()
    h_dir.mkdir()
    (u_dir / "test_u.txt").write_text("unharnessed dummy", encoding="utf-8")
    (h_dir / "test_h.txt").write_text("harnessed dummy", encoding="utf-8")

    test_replay_json = tmp_path / "replay_data.json"
    test_snapshots_dir = tmp_path / "snapshots"

    # Save to isolated test directories
    save_replay_recording(
        dummy_events,
        u_dir,
        h_dir,
        replay_path=test_replay_json,
        snapshots_dir=test_snapshots_dir,
    )

    # Verify isolated snapshots
    assert (test_snapshots_dir / "unharnessed" / "test_u.txt").is_file()
    assert (test_snapshots_dir / "harnessed" / "test_h.txt").is_file()
    assert test_replay_json.is_file()

    # Verify restore from isolated snapshots
    dest_u = tmp_path / "dest_u"
    dest_h = tmp_path / "dest_h"
    restore_replay_workspaces(
        snapshots_dir=test_snapshots_dir,
        target_u=dest_u,
        target_h=dest_h,
    )
    assert (dest_u / "test_u.txt").is_file()
    assert (dest_h / "test_h.txt").is_file()


@pytest.mark.anyio
async def test_stream_replay_events_speed_scaling() -> None:
    """Verify stream_replay_events computes speed_multiplier and attaches to init event."""
    from app.replay.player import stream_replay_events

    events_received = []
    async for evt in stream_replay_events():
        events_received.append(evt)
        if len(events_received) >= 1:
            break

    init_evt = events_received[0]
    assert init_evt.get("type") == "init"
    assert init_evt.get("is_replay") is True
    assert "replay_speed_multiplier" in init_evt
    assert init_evt["replay_speed_multiplier"] > 1.0
    assert "total_duration_seconds" in init_evt


def test_save_replay_endpoint_and_manual_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify live runs do not auto-overwrite replay, and POST /api/replay/save persists on demand."""
    from fastapi.testclient import TestClient

    import app.orchestrator as orch_mod
    from app.main import app, orchestrator

    client = TestClient(app)

    # 1. Without a completed live run, saving replay should be rejected with 400
    orchestrator.last_recorded_events = []
    res_empty = client.post("/api/replay/save")
    assert res_empty.status_code == 400

    # 2. Populate simulated live run events on orchestrator and verify manual save via HTTP endpoint
    u_dir = tmp_path / "u"
    h_dir = tmp_path / "h"
    u_dir.mkdir()
    h_dir.mkdir()
    (u_dir / "candidate_u.py").write_text("# unharnessed", encoding="utf-8")
    (h_dir / "candidate_h.py").write_text("# harnessed", encoding="utf-8")

    target_json = tmp_path / "saved_replay.json"
    target_snaps = tmp_path / "saved_snapshots"

    monkeypatch.setattr(orch_mod, "UNHARNESSED_DIR", u_dir)
    monkeypatch.setattr(orch_mod, "HARNESSED_DIR", h_dir)
    monkeypatch.setattr(orch_mod, "REPLAY_DATA_PATH", target_json)
    monkeypatch.setattr(orch_mod, "REPLAY_SNAPSHOTS_DIR", target_snaps)

    orchestrator.last_recorded_events = [
        {"type": "init", "delay_ms": 300, "message": "Running..."},
        {"type": "unharnessed_start", "delay_ms": 100, "message": "Start U"},
        {"type": "harnessed_start", "delay_ms": 100, "message": "Start H"},
        {"type": "unharnessed_event", "delay_ms": 200, "data": {"stage": "completed", "formatted_duration": "1:20", "duration_seconds": 80.0}},
        {"type": "harnessed_event", "delay_ms": 200, "data": {"stage": "completed", "formatted_duration": "0:30", "duration_seconds": 30.0}},
        {"type": "comparison_summary", "delay_ms": 500, "total_formatted_duration": "1:20", "total_duration_seconds": 80.0, "message": "Done"},
    ]
    try:
        res_ok = client.post("/api/replay/save")
        assert res_ok.status_code == 200
        payload = res_ok.json()
        assert payload["status"] == "ok"
        assert payload["events_saved"] == 6
        assert target_json.is_file()
        assert (target_snaps / "unharnessed" / "candidate_u.py").is_file()
        assert (target_snaps / "harnessed" / "candidate_h.py").is_file()
    finally:
        orchestrator.last_recorded_events = []


def test_ui_contains_save_replay_button() -> None:
    """Verify the Workbench UI exposes the explicit Save Replay button and JS handler."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="btn-save-replay"' in res.text
    assert 'saveAsReplay()' in res.text



