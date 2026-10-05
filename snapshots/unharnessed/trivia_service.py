from typing import Dict, Any, List

def get_trivia_for_sector(sector: str) -> Dict[str, Any]:
    # Vibe coding flaw: mixed real movies with generic sci-fi tropes
    if sector == "lv426":
        return {
            "question": "In the movie Alien (1979), what is the name of the commercial towing vessel?",
            "options": ["Nostromo", "Sulaco", "Prometheus", "Covenant"],
            "correct_index": 0,
            "movie_title": "Alien (1979)",
            "explanation": "The USCSS Nostromo was an M-Class lockheed starfreighter."
        }
    return {
        "question": "What is the speed of light in hyper-space warp drives?",
        "options": ["Warp 9", "C-fractional", "Instantaneous", "FTL"],
        "correct_index": 0,
        "movie_title": "Generic Space Lore",  # Flaw: Not a real Sci-Fi movie!
        "explanation": "Standard galactic propulsion measurement."
    }
