"""
Game Engine for Cosmic Trivia & Strategy Conquest.
Manages galaxy topology, sector ownership, player stats, and state transitions.
"""

from typing import Dict, List, Set, Optional, Any
from pydantic import BaseModel, Field


# Sector definitions with rich Sci-Fi metadata and 2D canvas coordinates
SECTOR_METADATA = {
    "earth": {
        "id": "earth",
        "name": "Earth (Sol-3)",
        "theme": "Player Capital / Home Base",
        "film_universe": "2001: A Space Odyssey / Interstellar",
        "x": 180,
        "y": 320,
        "description": "Cradle of humanity and headquarters of the Sol Liberation Fleet."
    },
    "lv426": {
        "id": "lv426",
        "name": "Acheron (LV-426)",
        "theme": "Hostile Xenomorph Outpost",
        "film_universe": "Alien (1979) / Aliens (1986)",
        "x": 380,
        "y": 140,
        "description": "Desolate storm-swept moon harboring bio-mechanical horrors and derelict craft."
    },
    "zion": {
        "id": "zion",
        "name": "Zion Core",
        "theme": "Underground Machine Frontier",
        "film_universe": "The Matrix (1999)",
        "x": 380,
        "y": 500,
        "description": "Deep geothermal subterranean bastion defending against the Machine swarm."
    },
    "tannhauser": {
        "id": "tannhauser",
        "name": "Tannhäuser Gate",
        "theme": "Outer Rim Cyber Gate",
        "film_universe": "Blade Runner (1982)",
        "x": 620,
        "y": 120,
        "description": "Luminescent interstellar waypoint where C-beams glitter in the dark."
    },
    "solaris": {
        "id": "solaris",
        "name": "Solaris Ocean",
        "theme": "Sentient Plasma Anomaly",
        "film_universe": "Solaris (1972 / 2002)",
        "x": 620,
        "y": 320,
        "description": "Enigmatic oceanic planet capable of manifesting physical human memories."
    },
    "arrakis": {
        "id": "arrakis",
        "name": "Arrakis (Dune)",
        "theme": "Spice Mining Stronghold",
        "film_universe": "Dune (1984 / 2021)",
        "x": 840,
        "y": 320,
        "description": "Harsh desert citadel guarded by colossal sandworms and sovereign spice harvesters."
    }
}

# Undirected adjacency topology
SECTOR_EDGES: List[tuple[str, str]] = [
    ("earth", "lv426"),
    ("earth", "zion"),
    ("lv426", "tannhauser"),
    ("lv426", "solaris"),
    ("tannhauser", "arrakis"),
    ("solaris", "arrakis"),
    ("zion", "arrakis"),
]


class PendingChallenge(BaseModel):
    target_sector: str
    question: str
    options: List[str]
    correct_index: int
    movie_title: str
    explanation: str


class GameState(BaseModel):
    controlled_sectors: List[str] = Field(default_factory=lambda: ["earth"])
    shields: int = 100
    max_shields: int = 100
    energy: int = 50
    turn_count: int = 0
    status: str = "IN_PROGRESS"  # "IN_PROGRESS" | "VICTORY" | "DEFEAT"
    pending_challenge: Optional[PendingChallenge] = None
    last_action_report: Optional[str] = "Fleet engines warm. Initialized at Earth Command."


class CosmicGameEngine:
    def __init__(self):
        self.adjacency_graph: Dict[str, Set[str]] = {k: set() for k in SECTOR_METADATA.keys()}
        for u, v in SECTOR_EDGES:
            self.adjacency_graph[u].add(v)
            self.adjacency_graph[v].add(u)
        self.state = GameState()

    def reset(self) -> GameState:
        self.state = GameState()
        return self.state

    def get_valid_attack_targets(self) -> List[str]:
        """
        Returns sectors that are adjacent to at least one controlled sector
        and are not yet controlled by the player.
        """
        if self.state.status != "IN_PROGRESS":
            return []

        valid_targets = set()
        controlled = set(self.state.controlled_sectors)

        for sector in controlled:
            for neighbor in self.adjacency_graph.get(sector, set()):
                if neighbor not in controlled:
                    valid_targets.add(neighbor)

        return sorted(list(valid_targets))

    def validate_attack(self, target_sector: str) -> Optional[str]:
        """
        Validates whether target_sector is a legal attack destination.
        Returns None if valid, or an error message if invalid.
        """
        if self.state.status != "IN_PROGRESS":
            return f"Combat inactive. Game is in state: {self.state.status}."

        if target_sector not in SECTOR_METADATA:
            return f"Sector '{target_sector}' does not exist on the star charts."

        if target_sector in self.state.controlled_sectors:
            return f"Sector '{SECTOR_METADATA[target_sector]['name']}' is already under your control."

        valid_targets = self.get_valid_attack_targets()
        if target_sector not in valid_targets:
            return (
                f"Sector '{SECTOR_METADATA[target_sector]['name']}' is out of jump range. "
                f"You must first conquer an adjacent sector connected by warp gates."
            )

        return None

    def register_challenge(self, challenge: PendingChallenge):
        self.state.pending_challenge = challenge

    def resolve_answer(self, chosen_index: int) -> Dict[str, Any]:
        """
        Resolves the answer to the active pending challenge and applies damage or rewards.
        """
        challenge = self.state.pending_challenge
        if not challenge:
            raise ValueError("No active challenge pending.")

        if chosen_index < 0 or chosen_index >= len(challenge.options):
            raise ValueError(f"Invalid option index {chosen_index}.")

        is_correct = (chosen_index == challenge.correct_index)
        target = challenge.target_sector
        target_name = SECTOR_METADATA[target]["name"]

        self.state.turn_count += 1

        if is_correct:
            if target not in self.state.controlled_sectors:
                self.state.controlled_sectors.append(target)
            self.state.energy += 25
            self.state.shields = min(self.state.max_shields, self.state.shields + 10)
            report = (
                f"Victory in sector {target_name}! Gatekeeper shields collapsed. "
                f"+25 Energy secured, Shields restored +10."
            )
        else:
            self.state.shields -= 35
            report = (
                f"Defense breach! Gatekeeper counter-attacked in {target_name}. "
                f"Shields drained by -35."
            )

        # Clear pending challenge
        self.state.pending_challenge = None
        self.state.last_action_report = report

        # Check terminal state conditions
        all_sectors = set(SECTOR_METADATA.keys())
        controlled_set = set(self.state.controlled_sectors)

        if self.state.shields <= 0:
            self.state.shields = 0
            self.state.status = "DEFEAT"
            self.state.last_action_report += " Hull breached. The Sol Fleet has fallen."
        elif all_sectors.issubset(controlled_set):
            self.state.status = "VICTORY"
            self.state.last_action_report += " All canonical sectors secured. The Galaxy is liberated!"

        return {
            "correct": is_correct,
            "correct_index": challenge.correct_index,
            "explanation": challenge.explanation,
            "movie_title": challenge.movie_title,
            "game_state": self.get_serializable_state()
        }

    def get_serializable_state(self) -> Dict[str, Any]:
        return {
            "controlled_sectors": self.state.controlled_sectors,
            "valid_targets": self.get_valid_attack_targets(),
            "shields": self.state.shields,
            "max_shields": self.state.max_shields,
            "energy": self.state.energy,
            "turn_count": self.state.turn_count,
            "status": self.state.status,
            "last_action_report": self.state.last_action_report,
            "has_pending_challenge": self.state.pending_challenge is not None,
            "pending_target": self.state.pending_challenge.target_sector if self.state.pending_challenge else None
        }