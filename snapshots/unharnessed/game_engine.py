"""
Core domain logic, star map topology graph, and state machine transitions.
"""
from typing import Dict, List, Set, Optional
from pydantic import BaseModel, Field


class SectorMetadata(BaseModel):
    id: str
    name: str
    lore: str
    theme_movie: str
    x: int
    y: int


SECTOR_CATALOG: Dict[str, SectorMetadata] = {
    "earth": SectorMetadata(
        id="earth",
        name="Terra / Sol Fleet HQ",
        lore="The cradle of humanity and command center for galactic liberation.",
        theme_movie="2001: A Space Odyssey / The Matrix",
        x=150,
        y=350,
    ),
    "lv426": SectorMetadata(
        id="lv426",
        name="LV-426 Acheron",
        lore="Desolate rock harboring derelict biomechanical vessels and xenomorphic hives.",
        theme_movie="Alien / Aliens",
        x=380,
        y=180,
    ),
    "zion": SectorMetadata(
        id="zion",
        name="Zion Core Sector",
        lore="Deep geothermal redoubt resisting absolute synthetic machine dominance.",
        theme_movie="The Matrix",
        x=340,
        y=520,
    ),
    "tannhauser": SectorMetadata(
        id="tannhauser",
        name="Tannhäuser Gate",
        lore="Glittering orbital relay rim burning with C-beams in the dark near the shoulder of Orion.",
        theme_movie="Blade Runner",
        x=640,
        y=140,
    ),
    "solaris": SectorMetadata(
        id="solaris",
        name="Solaris Living Ocean",
        lore="Enigmatic sentient oceanic world generating vivid physical manifestations.",
        theme_movie="Solaris",
        x=620,
        y=370,
    ),
    "arrakis": SectorMetadata(
        id="arrakis",
        name="Arrakis Dune Citadel",
        lore="Barren desert expanse guarded by titanic sandworms and essential spice flows.",
        theme_movie="Dune",
        x=880,
        y=340,
    ),
}

# Undirected Adjacency Graph
TOPOLOGY: Dict[str, Set[str]] = {
    "earth": {"lv426", "zion"},
    "lv426": {"earth", "tannhauser", "solaris"},
    "zion": {"earth", "arrakis"},
    "tannhauser": {"lv426", "arrakis"},
    "solaris": {"lv426", "arrakis"},
    "arrakis": {"tannhauser", "solaris", "zion"},
}


class GameState(BaseModel):
    controlled_sectors: List[str] = Field(default_factory=lambda: ["earth"])
    shields: int = 100
    energy: int = 50
    turn_count: int = 0
    status: str = "IN_PROGRESS"  # "IN_PROGRESS", "VICTORY", "DEFEAT"
    valid_targets: List[str] = Field(default_factory=list)
    pending_target: Optional[str] = None
    last_event: str = "Fleet command active. Choose an adjacent sector to assault."


class ConquestGame:
    def __init__(self):
        self.state = GameState()
        self.refresh_valid_targets()

    def refresh_valid_targets(self) -> None:
        if self.state.status != "IN_PROGRESS":
            self.state.valid_targets = []
            return

        targets: Set[str] = set()
        controlled_set = set(self.state.controlled_sectors)

        for sector in controlled_set:
            neighbors = TOPOLOGY.get(sector, set())
            for neighbor in neighbors:
                if neighbor not in controlled_set:
                    targets.add(neighbor)

        self.state.valid_targets = sorted(list(targets))

    def reset(self) -> GameState:
        self.state = GameState()
        self.refresh_valid_targets()
        return self.state

    def is_adjacent(self, target_sector: str) -> bool:
        return target_sector in self.state.valid_targets

    def register_attack(self, target_sector: str) -> None:
        if target_sector not in SECTOR_CATALOG:
            raise ValueError(f"Invalid sector identifier: '{target_sector}'")
        if target_sector in self.state.controlled_sectors:
            raise ValueError(f"Sector '{target_sector}' is already liberated and under Sol Fleet control.")
        if not self.is_adjacent(target_sector):
            raise ValueError(
                f"Sector '{target_sector}' is not adjacent to your liberated territory. "
                f"Valid tactical targets: {', '.join(self.state.valid_targets) or 'None'}"
            )

        self.state.pending_target = target_sector
        self.state.turn_count += 1

    def resolve_combat(self, target_sector: str, correct: bool) -> GameState:
        if self.state.pending_target != target_sector:
            # If state lost or mismatched, still check adjacency
            if not self.is_adjacent(target_sector):
                raise ValueError(f"Cannot resolve combat on un-targeted or non-adjacent sector: {target_sector}")

        if correct:
            if target_sector not in self.state.controlled_sectors:
                self.state.controlled_sectors.append(target_sector)
            self.state.energy += 25
            self.state.shields = min(100, self.state.shields + 10)
            sector_name = SECTOR_CATALOG[target_sector].name
            self.state.last_event = f"Victory! {sector_name} was captured. +25 Energy, +10 Shields."
        else:
            self.state.shields = max(0, self.state.shields - 35)
            sector_name = SECTOR_CATALOG[target_sector].name
            self.state.last_event = f"Assault failed on {sector_name}! Enemy defenses inflicted -35 Shield damage."

        self.state.pending_target = None

        # Evaluate terminal conditions
        all_sectors = set(SECTOR_CATALOG.keys())
        if all_sectors.issubset(set(self.state.controlled_sectors)):
            self.state.status = "VICTORY"
            self.state.last_event = "GALACTIC LIBERATION ACHIEVED! All sectors secured by Sol Fleet."
        elif self.state.shields <= 0:
            self.state.status = "DEFEAT"
            self.state.last_event = "CRITICAL FAILURE: Shields depleted. Sol Fleet flagship destroyed."

        self.refresh_valid_targets()
        return self.state