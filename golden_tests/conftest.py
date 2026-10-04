"""Pytest configuration fixture for dynamic candidate workspace testing."""

import os
import sys
from pathlib import Path

import pytest


@pytest.fixture
def candidate_workspace() -> Path:
    """Returns the path to the workspace currently undergoing evaluation."""
    target = os.environ.get("CANDIDATE_WORKSPACE_PATH")
    if not target:
        # Default fallback to workspaces/harnessed
        target = str(Path(__file__).resolve().parent.parent / "workspaces" / "harnessed")

    path = Path(target)
    if not (path / "game_engine.py").is_file():
        from app.agents.harnessed import (
            _apply_harnessed_self_healing_iteration_2,
            _write_harnessed_iteration_1,
        )

        _write_harnessed_iteration_1(path)
        _apply_harnessed_self_healing_iteration_2(path)

    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    return path

