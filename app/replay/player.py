"""Presentation Mode Replay Player.

Streams pre-recorded comparison trace events with realistic presentation pacing,
allowing seamless conference demonstrations without network dependencies.
"""

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any, AsyncGenerator

from app.agents.harnessed import (
    _apply_harnessed_self_healing_iteration_2,
    _write_harnessed_iteration_1,
)
from app.agents.unharnessed import _build_synthetic_unharnessed_app
from app.config import (
    HARNESSED_DIR,
    REPLAY_DATA_PATH,
    REPLAY_SNAPSHOTS_DIR,
    UNHARNESSED_DIR,
)


def restore_replay_workspaces(
    snapshots_dir: Path | None = None,
    target_u: Path | None = None,
    target_h: Path | None = None,
) -> None:
    """Populate candidate preview workspaces from saved snapshots or synthetic fallbacks."""
    source_snapshots_dir = snapshots_dir or REPLAY_SNAPSHOTS_DIR
    dest_u = target_u or UNHARNESSED_DIR
    dest_h = target_h or HARNESSED_DIR

    snap_u = source_snapshots_dir / "unharnessed"
    snap_h = source_snapshots_dir / "harnessed"

    # Restore unharnessed
    if snap_u.exists() and any(snap_u.iterdir()):
        if dest_u.exists():
            for item in dest_u.iterdir():
                if item.name == "README.md":
                    continue
                if item.is_file() or item.is_symlink():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
        dest_u.mkdir(parents=True, exist_ok=True)
        for item in snap_u.iterdir():
            dest = dest_u / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
    else:
        _build_synthetic_unharnessed_app(dest_u)

    # Restore harnessed
    if snap_h.exists() and any(snap_h.iterdir()):
        if dest_h.exists():
            for item in dest_h.iterdir():
                if item.name == "README.md":
                    continue
                if item.is_file() or item.is_symlink():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
        dest_h.mkdir(parents=True, exist_ok=True)
        for item in snap_h.iterdir():
            dest = dest_h / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
    else:
        _write_harnessed_iteration_1(dest_h)
        _apply_harnessed_self_healing_iteration_2(dest_h)

    # Populate living memory ledger for replay demonstrations
    from app.living_memory import LivingMemoryManager
    lm = LivingMemoryManager()
    lm.init_ledger(
        session_id="replay-presentation-session",
        goal_spec="Cosmic Trivia & Strategy Conquest (specs/cosmic_conquest_spec.md)",
    )
    lm.record_iteration(
        iteration=1,
        max_iterations=3,
        scorecard={
            "score": 10.0,
            "max_score": 14.0,
            "is_passing": False,
            "failed_checks": [
                {
                    "id": "SEC-01",
                    "name": "State Mutation Guard",
                    "details": "POST /api/action modifies persistent game state via unsafe direct assignment.",
                },
                {
                    "id": "ERR-02",
                    "name": "Structured JSON Error Payload",
                    "details": "Non-existent territory lookup triggered an unhandled KeyError rather than structured 404.",
                },
            ],
        },
        actions_taken=["game.py", "static/game.js", "tests/test_game.py"],
        strategy_notes="Isolate state mutations to pure transition handler. Wrap API endpoints in exception boundary to emit schema-compliant error envelopes.",
    )
    lm.record_iteration(
        iteration=2,
        max_iterations=3,
        scorecard={
            "score": 14.0,
            "max_score": 14.0,
            "is_passing": True,
            "failed_checks": [],
        },
        actions_taken=["game.py", "tests/test_game.py"],
        strategy_notes="All 14 rubric checks passed. Zero regressions detected. Deploying candidate build.",
    )


async def stream_replay_events() -> AsyncGenerator[dict[str, Any], None]:
    """Stream cached presentation replay events with authentic speed scaling."""
    # Ensure preview workspaces are populated with the demo files so preview tabs work immediately!
    restore_replay_workspaces()

    if not REPLAY_DATA_PATH.exists():
        yield {"type": "error", "message": "Replay data file not found."}
        return

    data = json.loads(REPLAY_DATA_PATH.read_text(encoding="utf-8"))
    events = data.get("events", [])

    total_replay_ms = sum(evt.get("delay_ms", 0) for evt in events)
    total_replay_sec = total_replay_ms / 1000.0 if total_replay_ms > 0 else 7.5

    summary_evt = next((e for e in events if e.get("type") == "comparison_summary"), None)
    auth_total_sec = summary_evt.get("total_duration_seconds", 120.0) if summary_evt else 120.0
    speed_multiplier = round(auth_total_sec / total_replay_sec, 2) if total_replay_sec > 0 else 16.0

    for evt in events:
        delay = evt.get("delay_ms", 500) / 1000.0
        await asyncio.sleep(delay)
        if evt.get("type") == "init":
            evt = dict(evt)
            evt["is_replay"] = True
            evt["replay_speed_multiplier"] = speed_multiplier
            evt["total_duration_seconds"] = auth_total_sec
        yield evt

