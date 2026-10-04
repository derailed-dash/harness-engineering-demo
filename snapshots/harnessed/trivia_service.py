"""Sci-Fi Movie Trivia Service providing challenges from canonical science fiction cinema.

Architectural Intent:
Encapsulates real movie trivia generation, guaranteeing that all questions are strictly
derived from real cinematic works (Blade Runner, 2001, Alien, The Matrix, Dune, Solaris).
"""

from typing import Any

CANONICAL_MOVIE_TRIVIA: dict[str, dict[str, Any]] = {
    "lv426": {
        "question": "In Ridley Scott's Alien (1979), what is the name of the commercial towing vessel?",
        "options": ["USCSS Nostromo", "USCSS Prometheus", "USS Sulaco", "USCSS Covenant"],
        "correct_index": 0,
        "movie_title": "Alien (1979)",
        "explanation": "The USCSS Nostromo was an M-Class commercial starfreighter owned by Weyland-Yutani.",
    },
    "tannhauser": {
        "question": "In Blade Runner (1982), Roy Batty famously recounts seeing C-beams glitter in the dark near which location?",
        "options": ["Tannhäuser Gate", "Orion's Shoulder", "Hadley's Hope", "The Tyrell Citadel"],
        "correct_index": 0,
        "movie_title": "Blade Runner (1982)",
        "explanation": "Roy Batty describes watching 'C-beams glitter in the dark near the Tannhäuser Gate'.",
    },
    "arrakis": {
        "question": "In Denis Villeneuve's Dune (2021), what sacred spice is harvested exclusively on Arrakis?",
        "options": ["Melange", "Tibanna", "Unobtanium", "Kyber"],
        "correct_index": 0,
        "movie_title": "Dune (2021)",
        "explanation": "Melange (the spice) extends life and makes interstellar space folding possible.",
    },
    "solaris": {
        "question": "In Andrei Tarkovsky's Solaris (1972), what is the sentient planet covered by?",
        "options": ["A vast gelatinous ocean", "Dense silicon forests", "Perpetual plasma storms", "Frozen methane oceans"],
        "correct_index": 0,
        "movie_title": "Solaris (1972)",
        "explanation": "Solaris is enveloped in a colloidal, thinking planetary ocean.",
    },
    "zion": {
        "question": "In The Matrix (1999), what is the name of Morpheus's hovercraft ship?",
        "options": ["Nebuchadnezzar", "Logos", "Osiris", "Mjolnir"],
        "correct_index": 0,
        "movie_title": "The Matrix (1999)",
        "explanation": "The Nebuchadnezzar is the iconic Mark III No. 479 hovercraft.",
    },
}

def get_trivia_for_sector(sector: str) -> dict[str, Any]:
    """Retrieve canonical movie trivia for target sector."""
    return CANONICAL_MOVIE_TRIVIA.get(sector, {
        "question": "In 2001: A Space Odyssey (1968), what is the sentient computer's name?",
        "options": ["HAL 9000", "Mother", "WOPR", "GERTY"],
        "correct_index": 0,
        "movie_title": "2001: A Space Odyssey (1968)",
        "explanation": "HAL 9000 is the Heuristically programmed ALgorithmic computer.",
    })
