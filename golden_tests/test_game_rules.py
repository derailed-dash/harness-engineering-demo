"""Golden acceptance test suite for Cosmic Conquest game rules.

Verifies the deterministic game mechanics, graph adjacency validation, turn resolution,
shield depletion, and terminal conditions.
"""

from typing import Any


def get_game_engine_module(workspace_path: Any) -> Any:
    """Dynamically import game_engine from the candidate workspace."""
    import sys
    from importlib import import_module
    
    str_path = str(workspace_path)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)
    
    return import_module("game_engine")


def test_initial_state(candidate_workspace: Any) -> None:
    """Verify pristine game initialisation state."""
    engine = get_game_engine_module(candidate_workspace)
    state = engine.get_initial_state()
    
    assert state["controlled_sectors"] == ["earth"]
    assert state["shields"] == 100
    assert state["energy"] == 50
    assert state["status"] == "IN_PROGRESS"


def test_adjacency_validation(candidate_workspace: Any) -> None:
    """Verify that only directly adjacent sectors can be attacked."""
    engine = get_game_engine_module(candidate_workspace)
    state = engine.get_initial_state()
    
    # Earth is adjacent to lv426 and zion
    assert engine.can_attack_sector(state, "lv426") is True
    assert engine.can_attack_sector(state, "zion") is True
    
    # Earth is NOT adjacent to arrakis, tannhauser, or solaris
    assert engine.can_attack_sector(state, "arrakis") is False
    assert engine.can_attack_sector(state, "tannhauser") is False
    assert engine.can_attack_sector(state, "solaris") is False


def test_successful_attack_conquers_sector(candidate_workspace: Any) -> None:
    """Verify that answering correctly captures the sector and awards bonuses."""
    engine = get_game_engine_module(candidate_workspace)
    state = engine.get_initial_state()
    
    updated_state, message = engine.resolve_combat(state, target_sector="lv426", is_correct=True)
    
    assert "lv426" in updated_state["controlled_sectors"]
    assert updated_state["energy"] > 50
    assert updated_state["status"] == "IN_PROGRESS"


def test_failed_attack_damages_shields(candidate_workspace: Any) -> None:
    """Verify that a wrong answer penalises shields and does not capture sector."""
    engine = get_game_engine_module(candidate_workspace)
    state = engine.get_initial_state()
    
    updated_state, message = engine.resolve_combat(state, target_sector="lv426", is_correct=False)
    
    assert "lv426" not in updated_state["controlled_sectors"]
    assert updated_state["shields"] < 100
    assert updated_state["status"] == "IN_PROGRESS"


def test_defeat_condition_when_shields_reach_zero(candidate_workspace: Any) -> None:
    """Verify defeat state triggers when shields fall to 0."""
    engine = get_game_engine_module(candidate_workspace)
    state = engine.get_initial_state()
    state["shields"] = 10
    
    updated_state, _ = engine.resolve_combat(state, target_sector="lv426", is_correct=False)
    assert updated_state["shields"] <= 0
    assert updated_state["status"] == "DEFEAT"


def test_victory_condition_when_all_sectors_captured(candidate_workspace: Any) -> None:
    """Verify victory state triggers when all 6 sectors are captured."""
    engine = get_game_engine_module(candidate_workspace)
    state = engine.get_initial_state()
    state["controlled_sectors"] = ["earth", "lv426", "tannhauser", "arrakis", "solaris"]
    
    updated_state, _ = engine.resolve_combat(state, target_sector="zion", is_correct=True)
    assert "zion" in updated_state["controlled_sectors"]
    assert updated_state["status"] == "VICTORY"
