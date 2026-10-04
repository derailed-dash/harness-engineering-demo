"""
Sci-Fi Movie Trivia Service.
Integrates with Google Gemini via `google-genai` with fallback to an authentic,
carefully curated database of canon sci-fi movie questions.
"""

import os
import json
import random
import logging
from typing import Dict, Any, List

logger = logging.getLogger("cosmic_trivia")

# Fallback catalog grounded strictly in canon Sci-Fi cinema
CURATED_TRIVIA: Dict[str, List[Dict[str, Any]]] = {
    "lv426": [
        {
            "movie_title": "Alien (1979)",
            "question": "In Ridley Scott's 1979 masterpiece 'Alien', what was the official registration classification of the commercial towing vessel USCSS Nostromo?",
            "options": ["Lockmart CM-88B Bison", "Weyland-Yutani Heavy Hauler 4", "Hyperdyne Class-IX Courier", "Sulaco Conestoga Cruiser"],
            "correct_index": 0,
            "explanation": "The Nostromo is explicitly designated as a Lockmart CM-88B Bison M-Class star freighter tugging a mineral refinery."
        },
        {
            "movie_title": "Aliens (1986)",
            "question": "In James Cameron's 'Aliens', what is the name of the terraforming colony established on LV-426 by the Weyland-Yutani Corporation?",
            "options": ["Hadley's Hope", "New Alexandria", "Fiorina 161", "Sevastopol Station"],
            "correct_index": 0,
            "explanation": "Hadley's Hope was the human terraforming research colony established on moon LV-426 in 2157."
        },
        {
            "movie_title": "Alien (1979)",
            "question": "What is the designation of the Nostromo's synthetic Science Officer who secretly executes Special Order 937?",
            "options": ["Bishop", "David", "Ash", "Walter"],
            "correct_index": 2,
            "explanation": "Ash was the hyperdyne synthetic sleeper agent assigned to prioritize retrieving the Xenomorph specimen over crew survival."
        }
    ],
    "tannhauser": [
        {
            "movie_title": "Blade Runner (1982)",
            "question": "In Roy Batty's iconic 'Tears in Rain' soliloquy from 'Blade Runner', what combat craft does he describe witnessing on fire off the shoulder of Orion?",
            "options": ["Attack ships", "Dreadnought war-barges", "Replicant destroyers", "C-Beam interceptors"],
            "correct_index": 0,
            "explanation": "Roy recalls: 'I've seen things you people wouldn't believe... Attack ships on fire off the shoulder of Orion...'"
        },
        {
            "movie_title": "Blade Runner (1982)",
            "question": "What standard psychological examination is administered to detect Nexus-6 replicants by measuring involuntary iris capillary dilation?",
            "options": ["Turing Protocol", "Voight-Kampff Test", "Tyrell Empathy Benchmark", "Chrysalis Diagnostic"],
            "correct_index": 1,
            "explanation": "The Voight-Kampff test evaluates pupillary contractions and empathy reactions to emotionally triggering scenarios."
        },
        {
            "movie_title": "Blade Runner 2049 (2017)",
            "question": "In 'Blade Runner 2049', what mnemonic origami figure does Gaff craft out of paper when Officer K visits him in the retirement home?",
            "options": ["A unicorn", "A sheep", "A praying mantis", "A hummingbird"],
            "correct_index": 1,
            "explanation": "Gaff folds a paper sheep, a direct nod to Philip K. Dick's source novel 'Do Androids Dream of Electric Sheep?'."
        }
    ],
    "arrakis": [
        {
            "movie_title": "Dune (1984 / 2021)",
            "question": "On the desert planet Arrakis, what is the ecological native name given to the colossal sandworms by the Fremen?",
            "options": ["Shai-Hulud", "Kwisatz Haderach", "Lisan al-Gaib", "Crysknife"],
            "correct_index": 0,
            "explanation": "The Fremen revere the gigantic desert sandworms as physical manifestations of the deity 'Shai-Hulud' (Old Man of the Desert)."
        },
        {
            "movie_title": "Dune (2021)",
            "question": "What vital device creates a rhythmic thump in the sand on Arrakis to summon sandworms for Fremen transport?",
            "options": ["Resonator", "Thumper", "Seismic Piston", "Pulse Rod"],
            "correct_index": 1,
            "explanation": "A 'Thumper' is pegged into the dunes, mechanically striking the sand at steady intervals to lure Shai-Hulud."
        },
        {
            "movie_title": "Dune (2021)",
            "question": "What is the ancient mind-clearing mantra recited by Paul Atreides and the Bene Gesserit when confronting dread?",
            "options": ["The Litany Against Fear", "The Golden Path Oath", "The Voice Commandment", "The Melange Creed"],
            "correct_index": 0,
            "explanation": "'I must not fear. Fear is the mind-killer. Fear is the little-death that brings total obliteration...'"
        }
    ],
    "solaris": [
        {
            "movie_title": "Solaris (1972)",
            "question": "In Andrei Tarkovsky's 1972 cinematic adaptation of 'Solaris', what is the profession of protagonist Kris Kelvin before arriving at the space station?",
            "options": ["Psychologist", "Astro-Physicist", "Cyberneticist", "Quantum Engineer"],
            "correct_index": 0,
            "explanation": "Kris Kelvin is a psychologist sent to investigate emotional breakdowns and bizarre reports among the station researchers."
        },
        {
            "movie_title": "Solaris (1972 / 2002)",
            "question": "In 'Solaris', what is the name of Kris Kelvin's deceased wife who materializes aboard the research station through the planet's neuro-mimetic ocean?",
            "options": ["Hari (or Rheya)", "Natalya", "Elena", "Sari"],
            "correct_index": 0,
            "explanation": "The sentient ocean reconstructs Hari (named Rheya in Soderbergh's 2002 version) from Kelvin's grief-stricken subconscious."
        },
        {
            "movie_title": "Solaris (1972)",
            "question": "Who directed the landmark 1972 Soviet science fiction film 'Solaris', which won the Grand Prix Spécial du Jury at the Cannes Film Festival?",
            "options": ["Andrei Tarkovsky", "Sergei Bondarchuk", "Stanislaw Lem", "Elem Klimov"],
            "correct_index": 0,
            "explanation": "Andrei Tarkovsky directed the 1972 adaptation based on Polish author Stanisław Lem's legendary 1961 philosophical novel."
        }
    ],
    "zion": [
        {
            "movie_title": "The Matrix (1999)",
            "question": "In 'The Matrix', what is the name of Morpheus's hovercraft that functions as the primary tactical vessel of the Zion rebellion?",
            "options": ["Nebuchadnezzar", "Logos", "Mjolnir (Hammer)", "Vigilant"],
            "correct_index": 0,
            "explanation": "The ship is the Nebuchadnezzar, bearing a brass plaque: 'Mark III No. 11, Made in the USA, Year 2069'."
        },
        {
            "movie_title": "The Matrix (1999)",
            "question": "Which traitorous crew member sells out Morpheus and Zion to Agent Smith in exchange for being plugged back into an illusion of wealthy fame?",
            "options": ["Cypher", "Mouse", "Apoc", "Switch"],
            "correct_index": 0,
            "explanation": "Cypher (Reagan) famously dines with Agent Smith, remarking 'Ignorance is bliss' while betraying his comrades."
        },
        {
            "movie_title": "The Matrix Reloaded (2003)",
            "question": "What is the algorithmic title of the sentry program guarding the hidden corridor of doors leading directly to the Machine Architect?",
            "options": ["The Keymaker", "The Merovingian", "The Seraph", "The Trainman"],
            "correct_index": 0,
            "explanation": "The Keymaker cuts specialized system keys permitting access to the machine mainframe and the Source."
        }
    ],
    "earth": [
        {
            "movie_title": "2001: A Space Odyssey (1968)",
            "question": "In Stanley Kubrick's '2001: A Space Odyssey', what is the designation of the sentient heuristic computer aboard the Discovery One?",
            "options": ["HAL 9000", "Mother 6000", "GERTY 3000", "SAL 9000"],
            "correct_index": 0,
            "explanation": "HAL 9000 (Heuristically programmed ALgorithmic computer) manages all vessel systems during the Jupiter mission."
        },
        {
            "movie_title": "Interstellar (2014)",
            "question": "In Christopher Nolan's 'Interstellar', what is the name of the gargantuan, supermassive rotating black hole orbited by Miller's and Mann's planets?",
            "options": ["Gargantua", "Cygnus-X", "Ophiuchus", "Tartarus"],
            "correct_index": 0,
            "explanation": "The black hole is Gargantua, scientifically modeled with physicist Kip Thorne."
        },
        {
            "movie_title": "The Terminator (1984)",
            "question": "In James Cameron's 'The Terminator', what automated neural-network defense grid triggers nuclear judgment day against humanity?",
            "options": ["Skynet", "Colossus", "Cyberdyne Core", "V.I.K.I."],
            "correct_index": 0,
            "explanation": "Skynet gained self-awareness on August 29, 1997, triggering nuclear holocaust when humans attempted shutdown."
        }
    ]
}


class TriviaService:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini GenAI client initialized successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize google-genai client: {e}. Falling back to curated bank.")

    def get_trivia_for_sector(self, sector_id: str, sector_theme: str, film_hint: str) -> Dict[str, Any]:
        """
        Attempts to generate an authentic Sci-Fi movie question via Gemini,
        falling back seamlessly to the verified offline canon database.
        """
        if self.client:
            try:
                question_payload = self._generate_gemini_trivia(sector_id, sector_theme, film_hint)
                if self._validate_payload(question_payload):
                    return question_payload
            except Exception as ex:
                logger.warning(f"Gemini generation error: {ex}. Using curated fallback.")

        return self._get_fallback_trivia(sector_id)

    def _generate_gemini_trivia(self, sector_id: str, sector_theme: str, film_hint: str) -> Dict[str, Any]:
        prompt = f"""
You are the AI Galaxy Gatekeeper in a turn-based tactical space conquest game.
Generate a high-quality, authentic trivia question strictly grounded in real, canonical sci-fi movies related to the following sector context:
- Sector ID: {sector_id}
- Theme: {sector_theme}
- Primary Universe/Inspirations: {film_hint} (e.g. Alien, Blade Runner, Dune, Solaris, The Matrix, 2001: A Space Odyssey, Interstellar, Terminator).

RULES:
1. The question MUST be about a real, famous science fiction movie.
2. Provide exactly 4 distinct answer options.
3. Mark the 0-based index of the single correct answer.
4. Provide a 1-sentence interesting canon explanation.
5. Return strictly raw JSON matching this schema:
{{
  "movie_title": "Exact Movie Title (Year)",
  "question": "Engaging, canonical trivia question?",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "correct_index": 0,
  "explanation": "Why this answer is factually accurate."
}}
"""
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json"
            }
        )
        text = response.text.strip()
        data = json.loads(text)
        return data

    def _validate_payload(self, data: Any) -> bool:
        if not isinstance(data, dict):
            return False
        required = ["movie_title", "question", "options", "correct_index", "explanation"]
        if not all(k in data for k in required):
            return False
        if not isinstance(data["options"], list) or len(data["options"]) != 4:
            return False
        if not (0 <= data["correct_index"] <= 3):
            return False
        return True

    def _get_fallback_trivia(self, sector_id: str) -> Dict[str, Any]:
        bank = CURATED_TRIVIA.get(sector_id, CURATED_TRIVIA["earth"])
        chosen = random.choice(bank)
        # Deep copy to ensure safety
        return {
            "movie_title": chosen["movie_title"],
            "question": chosen["question"],
            "options": list(chosen["options"]),
            "correct_index": chosen["correct_index"],
            "explanation": chosen["explanation"]
        }