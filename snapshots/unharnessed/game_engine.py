from typing import List, Dict, Any

# Simple game engine for space trivia
class StarMap:
    def __init__(self):
        self.sectors = ["earth", "lv426", "tannhauser", "arrakis", "solaris", "zion"]
        self.controlled = ["earth"]
        self.shields = 100
        self.energy = 50
        self.status = "IN_PROGRESS"

def get_initial_state() -> Dict[str, Any]:
    return {
        "controlled_sectors": ["earth"],
        "shields": 100,
        "energy": 50,
        "status": "IN_PROGRESS",
        "available_targets": ["lv426", "zion", "arrakis"]  # Flaw: included non-adjacent arrakis!
    }

def can_attack_sector(state: Dict[str, Any], target: str) -> bool:
    # Vibe coding flaw: loosely checks if target exists instead of strict adjacency graph
    return target in ["lv426", "zion", "arrakis", "tannhauser", "solaris"]

def resolve_combat(state: Dict[str, Any], target_sector: str, is_correct: bool) -> tuple[Dict[str, Any], str]:
    if is_correct:
        if target_sector not in state["controlled_sectors"]:
            state["controlled_sectors"].append(target_sector)
        state["energy"] += 20
        if len(state["controlled_sectors"]) >= 6:
            state["status"] = "VICTORY"
        return state, f"Sector {target_sector} captured!"
    else:
        state["shields"] -= 30
        if state["shields"] <= 0:
            state["status"] = "DEFEAT"
        return state, "Shields hit!"
