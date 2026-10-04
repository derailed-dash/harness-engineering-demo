"""Game engine module managing star map topology, territory conquest, and turn state machines.

Architectural Intent:
Pure domain logic independent of HTTP transports, enabling deterministic unit testing
and state serialization for the Cosmic Conquest game.
"""

from typing import Any

# Canonical sector connectivity graph
STAR_MAP_GRAPH: dict[str, list[str]] = {
    "earth": ["lv426", "zion"],
    "lv426": ["earth", "tannhauser", "solaris"],
    "tannhauser": ["lv426", "arrakis"],
    "arrakis": ["tannhauser", "solaris", "zion"],
    "solaris": ["lv426", "arrakis"],
    "zion": ["earth", "arrakis"],
}

ALL_SECTORS = list(STAR_MAP_GRAPH.keys())

def get_initial_state() -> dict[str, Any]:
    """Create pristine initial game state."""
    return {
        "controlled_sectors": ["earth"],
        "shields": 100,
        "energy": 50,
        "status": "IN_PROGRESS",
        "turn": 1,
    }

def get_available_targets(state: dict[str, Any]) -> list[str]:
    """Compute unconquered sectors directly adjacent to controlled territory."""
    controlled = set(state["controlled_sectors"])
    targets: set[str] = set()
    for sector in controlled:
        for neighbour in STAR_MAP_GRAPH.get(sector, []):
            if neighbour not in controlled:
                targets.add(neighbour)
    return sorted(list(targets))

def can_attack_sector(state: dict[str, Any], target_sector: str) -> bool:
    """Validate that target sector is adjacent to current territory."""
    return target_sector in get_available_targets(state)

def resolve_combat(state: dict[str, Any], target_sector: str, is_correct: bool) -> tuple[dict[str, Any], str]:
    """Resolve turn mechanics based on trivia response."""
    state["turn"] += 1
    if is_correct:
        if target_sector not in state["controlled_sectors"]:
            state["controlled_sectors"].append(target_sector)
        state["energy"] += 25
        state["shields"] = min(100, state["shields"] + 10)
        
        if len(state["controlled_sectors"]) >= len(ALL_SECTORS):
            state["status"] = "VICTORY"
            return state, "Victory! The entire galaxy has been liberated."
        return state, f"Success! Sector {target_sector.upper()} captured."
    else:
        state["shields"] -= 35
        if state["shields"] <= 0:
            state["status"] = "DEFEAT"
            return state, "Critical failure: Shields depleted. Game over."
        return state, f"Defeat in sector {target_sector.upper()}. Shields hit."
