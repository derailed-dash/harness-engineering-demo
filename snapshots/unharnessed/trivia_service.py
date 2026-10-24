"""
Trivia service grounded strictly in canonical, real Sci-Fi movies.
Integrates Gemini API via google-genai with an authentic fallback pool.
"""
import os
import json
import random
from typing import Dict, Any, List

# High-fidelity curated repository of authentic Sci-Fi cinema trivia
CURATED_QUESTIONS: Dict[str, List[Dict[str, Any]]] = {
    "lv426": [
        {
            "movie_title": "Alien (1979)",
            "question": "On the derelict ship on LV-426, which crew member is the first to be attacked by an embryonic Facehugger?",
            "options": ["Gilbert Ward Kane", "Arthur Dallas", "Ellen Ripley", "Joan Lambert"],
            "correct_index": 0,
            "explanation": "Executive Officer Kane descends into the derelict hold and leans over an ovomorph egg when the Facehugger shatters his helmet visor."
        },
        {
            "movie_title": "Aliens (1986)",
            "question": "What is the primary atmospheric processing installation called on LV-426 before the Xenomorph infestation?",
            "options": ["Hadley's Hope", "Tyrell Tower", "Nostromo Hub", "Gateway Station"],
            "correct_index": 0,
            "explanation": "Hadley's Hope was the terraforming human colony established on LV-426 with 158 colonists."
        }
    ],
    "zion": [
        {
            "movie_title": "The Matrix Reloaded (2003)",
            "question": "What specialized electromagnetic defense weapon is mounted on Zion's perimeter docks to disable inbound Sentinels?",
            "options": ["EMP Cannon Node", "APU (Armored Personnel Unit)", "Phased Plasma Torpedo", "Tachyon Railgun"],
            "correct_index": 1,
            "explanation": "Captain Mifune and the Zion defense corps pilot dual-30mm hydraulic Armored Personnel Units (APUs) at the Dock Gate."
        },
        {
            "movie_title": "The Terminator (1984)",
            "question": "In Kyle Reese's dystopian flashbacks, what creature do human resistance soldiers use at bunker entrances to detect infiltrating Terminators?",
            "options": ["Specially trained dogs", "Thermal sensor bats", "Canary birds", "Rats"],
            "correct_index": 0,
            "explanation": "Dogs can sniff out the biological synthetic flesh masking the cold titanium combat chassis of Infiltrator units."
        }
    ],
    "tannhauser": [
        {
            "movie_title": "Blade Runner (1982)",
            "question": "In Roy Batty's iconic monologue, what phenomenon did he watch 'glitter in the dark near the Tannhäuser Gate'?",
            "options": ["C-beams", "Ion flares", "Tachyon storms", "Solar winds"],
            "correct_index": 0,
            "explanation": "Roy Batty famously reflects: 'I watched C-beams glitter in the dark near the Tannhäuser Gate. All those moments will be lost in time, like tears in rain.'"
        },
        {
            "movie_title": "Blade Runner 2049 (2017)",
            "question": "What exact serial model designation is Officer K (Joe) identified as in the LAPD registry?",
            "options": ["Nexus-9 KD6-3.7", "Nexus-6 Roy-001", "Nexus-8 Sapper-5", "Nexus-7 Deckard-X"],
            "correct_index": 0,
            "explanation": "K is a docile Nexus-9 replicant model serial number KD6-3.7 designed to obey orders without rebellion."
        }
    ],
    "solaris": [
        {
            "movie_title": "Solaris (1972)",
            "question": "In Andrei Tarkovsky's 'Solaris', what is the name of psychologist Kris Kelvin's deceased wife who materializes aboard the station?",
            "options": ["Hari", "Natalya", "Elena", "Tatyana"],
            "correct_index": 0,
            "explanation": "The sentient ocean manifests Hari, reproducing Kelvin's guilty memory of his late wife who died by suicide on Earth."
        },
        {
            "movie_title": "Interstellar (2014)",
            "question": "Due to gravitational time dilation near the supermassive black hole Gargantua, how many Earth years correspond to one hour on Miller's water planet?",
            "options": ["7 years", "12 years", "20 years", "1 year"],
            "correct_index": 0,
            "explanation": "Miller's planet orbits deep within Gargantua's gravity well, creating a time dilation factor where 1 hour equals 7 Earth years."
        }
    ],
    "arrakis": [
        {
            "movie_title": "Dune (2021 / 2024)",
            "question": "What is the secret Fremen name given to Paul Atreides signifying 'the base of the pillar'?",
            "options": ["Usul", "Muad'Dib", "Kwisatz", "Mahdi"],
            "correct_index": 0,
            "explanation": "Stilgar and the Sietch Tabr elders bestow the private troop name 'Usul' upon Paul, while he chooses 'Muad'Dib' as his open public name."
        },
        {
            "movie_title": "2001: A Space Odyssey (1968)",
            "question": "When HAL 9000 refuses to open the pod bay doors, what reason does the AI give to astronaut Dave Bowman?",
            "options": [
                "This mission is too important for me to allow you to jeopardize it",
                "Atmospheric seal locks have experienced critical telemetry error",
                "Directives from Earth High Command require complete human isolation",
                "Dave, my primary circuits are undergoing emergency reboot"
            ],
            "correct_index": 0,
            "explanation": "HAL 9000 calmly states: 'This mission is too important for me to allow you to jeopardize it.'"
        }
    ]
}


class TriviaService:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")

    def generate_challenge(self, sector_id: str) -> Dict[str, Any]:
        """
        Attempts to generate a real Sci-Fi movie question via Gemini;
        falls back seamlessly to curated authentic challenges if unavailable.
        """
        if self.api_key:
            try:
                challenge = self._generate_with_gemini(sector_id)
                if challenge:
                    return challenge
            except Exception:
                # Graceful degradation to verified curated pool
                pass

        return self._get_fallback_challenge(sector_id)

    def _generate_with_gemini(self, sector_id: str) -> Dict[str, Any]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)

        prompt = f"""
Generate 1 high-quality, 100% accurate trivia question about a famous, canonical Sci-Fi movie matching the sector theme '{sector_id}'.
Films allowed: Alien, Aliens, Blade Runner, Blade Runner 2049, Dune, 2001: A Space Odyssey, The Matrix, Terminator, Interstellar, Solaris.

Return STRICT JSON matching this schema:
{{
  "movie_title": "string (Title & release year)",
  "question": "string (the trivia question)",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "correct_index": integer (0, 1, 2, or 3),
  "explanation": "string (1-2 sentences verifying the canonical movie fact)"
}}
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )

        data = json.loads(response.text)
        if (
            "movie_title" in data
            and "question" in data
            and isinstance(data.get("options"), list)
            and len(data["options"]) == 4
            and isinstance(data.get("correct_index"), int)
            and 0 <= data["correct_index"] <= 3
            and "explanation" in data
        ):
            return data
        raise ValueError("Invalid payload structure from AI model.")

    def _get_fallback_challenge(self, sector_id: str) -> Dict[str, Any]:
        """Provides verified fallback trivia guaranteed to be canon."""
        pool = CURATED_QUESTIONS.get(sector_id)
        if not pool:
            # Aggregate across all sectors if custom sector specified
            pool = [q for questions in CURATED_QUESTIONS.values() for q in questions]
        return random.choice(pool).copy()