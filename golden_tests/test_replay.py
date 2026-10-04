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


