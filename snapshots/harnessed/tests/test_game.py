"""TDD Unit test suite for Cosmic Conquest game rules."""

import pytest
import game_engine

def test_initial_state():
    state = game_engine.get_initial_state()
    assert state["controlled_sectors"] == ["earth"]
    assert state["shields"] == 100
    assert state["status"] == "IN_PROGRESS"

def test_adjacency_check():
    state = game_engine.get_initial_state()
    assert game_engine.can_attack_sector(state, "lv426") is True
    assert game_engine.can_attack_sector(state, "arrakis") is False

def test_combat_resolution():
    state = game_engine.get_initial_state()
    new_state, _ = game_engine.resolve_combat(state, "lv426", is_correct=True)
    assert "lv426" in new_state["controlled_sectors"]
    assert new_state["energy"] > 50
