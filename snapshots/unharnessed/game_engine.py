"""
Game Engine for Cosmic Trivia & Strategy Conquest.
Manages galaxy topology, state machine transitions, and turn evaluations.
"""
from typing import Dict, List, Set, Any, Optional

SECTOR_METADATA: Dict[str, Dict[str, Any]] = {
    "earth": {
        "name": "Earth - Sol Capital",
        "theme": "The Matrix & 2001: A Space Odyssey",
        "description": "Humanity's cradle and high-command staging ground.",
        "coords": {"x": 150, "y": 300}
    },
    "lv426": {
        "name": "Acheron LV-426",
        "theme": "Alien & Aliens",
        "description": "Desolate storm-swept moon hosting bio-mechanical terrors.",
        "coords": {"x": 380, "y": 140}
    },
    "zion": {
        "name": "Zion Sub-Level",
        "theme": "The Matrix & Terminator",
        "description": "Subterranean bastion besieged by sentinel swarm constructs.",
        "coords": {"x": 380, "y": 460}
    },
    "tannhauser": {
        "name": "Tannhäuser Gate",
        "theme": "Blade Runner",
        "description": "Outer-rim warp relay glowing with c-beams in the dark.",
        "coords": {"x": 620, "y": 140}
    },
    "solaris": {
        "name": "Solaris Ocean Orbit",
        "theme": "Solaris & Interstellar",
        "description": "Living plasma ocean inducing psycho-physical apparitions.",
        "coords": {"x": 620, "y": 300}
    },
    "arrakis": {
        "name": "Arrakis Deep Desert",
        "theme": "Dune",
        "description": "Harsh spice citadel and AI Gatekeeper command core.",
        "coords": {"x": 850, "y": 300}
    }
}

# Star Map Topology: Undirected Graph Adjacency List
GALAXY_GRAPH: Dict[str, List[str]] = {
    "earth": ["lv426", "zion"],
    "lv426": ["earth", "tannhauser", "solaris"],
    "zion": ["earth", "arrakis"],
    "tannhauser": ["lv426", "arrakis"],
    "solaris": ["lv426", "arrakis"],
    "arrakis": ["tannhauser", "solaris", "zion"]
}

TOTAL_SECTORS: int = len(SECTOR_METADATA)


class GameState:
    def __init__(self):
        self.controlled_sectors: List[str] = ["earth"]
        self.shields: int = 100
        self.energy: int = 50
        self.turn_count: int = 0
        self.status: str = "IN_PROGRESS"  # "IN_PROGRESS", "VICTORY", "DEFEAT"
        self.active_challenge: Optional[Dict[str, Any]] = None

    def get_valid_targets(self) -> List[str]:
        """Returns unconquered sectors directly adjacent to player-held territory."""
        if self.status != "IN_PROGRESS":
            return []

        controlled_set = set(self.controlled_sectors)
        candidates: Set[str] = set()

        for sector in self.controlled_sectors:
            for neighbor in GALAXY_GRAPH.get(sector, []):
                if neighbor not in controlled_set:
                    candidates.add(neighbor)

        return sorted(list(candidates))

    def can_attack(self, target_sector: str) -> tuple[bool, str]:
        """Validates if target sector is eligible for invasion."""
        if self.status != "IN_PROGRESS":
            return False, f"Campaign has concluded with status: {self.status}."

        if target_sector not in SECTOR_METADATA:
            return False, f"Unknown sector identifier: '{target_sector}'."

        if target_sector in self.controlled_sectors:
            return False, f"Sector '{target_sector}' is already under Sol Fleet control."

        valid_targets = self.get_valid_targets()
        if target_sector not in valid_targets:
            return False, (
                f"Sector '{target_sector}' is not adjacent to your territory. "
                f"Valid targets: {', '.join(valid_targets) if valid_targets else 'None'}."
            )

        return True, "Target is valid."

    def resolve_combat(self, target_sector: str, is_correct: bool) -> Dict[str, Any]:
        """Updates internal status based on combat resolution."""
        self.turn_count += 1
        summary = {}

        if is_correct:
            if target_sector not in self.controlled_sectors:
                self.controlled_sectors.append(target_sector)
            self.energy += 25
            self.shields = min(100, self.shields + 10)
            summary["outcome"] = "CONQUERED"
            summary["message"] = f"Decryption key verified! {SECTOR_METADATA[target_sector]['name']} liberated."
        else:
            self.shields -= 35
            summary["outcome"] = "DEFENSE_REPUDIATED"
            summary["message"] = f"Cyber-defense breach failed. Sol Fleet shields compromised by 35%."

        # Terminal conditions evaluation
        if len(self.controlled_sectors) >= TOTAL_SECTORS:
            self.status = "VICTORY"
            summary["message"] += " All galactic sectors secured. Humanity triumphs!"
        elif self.shields <= 0:
            self.shields = 0
            self.status = "DEFEAT"
            summary["message"] += " Fleet shields fully depleted. The Gatekeeper AI maintains dominance."

        # Clear pending challenge
        self.active_challenge = None

        return summary

    def to_dict(self) -> Dict[str, Any]:
        return {
            "controlled_sectors": self.controlled_sectors,
            "shields": self.shields,
            "energy": self.energy,
            "turn_count": self.turn_count,
            "status": self.status,
            "valid_targets": self.get_valid_targets(),
            "sector_metadata": SECTOR_METADATA,
            "adjacency_graph": GALAXY_GRAPH,
            "total_sectors": TOTAL_SECTORS,
        }