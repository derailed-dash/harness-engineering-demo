"""
Cinematic Sci-Fi trivia challenge generator and validator.
Integrates google-genai with high-fidelity authentic curated fallbacks.
"""
import os
import random
import json
from typing import Dict, List, Optional
from pydantic import BaseModel

try:
    from google import genai
except ImportError:
    genai = None


class TriviaChallenge(BaseModel):
    sector_id: str
    movie_title: str
    question: str
    options: List[str]
    correct_index: int
    explanation: str


CURATED_TRIVIA: Dict[str, List[TriviaChallenge]] = {
    "lv426": [
        TriviaChallenge(
            sector_id="lv426",
            movie_title="Alien (1979)",
            question="What is the name of the commercial towing starship directed to investigate the beacon on LV-426?",
            options=["USCSS Nostromo", "USS Sulaco", "Discovery One", "USSC Prometheus"],
            correct_index=0,
            explanation="The crew of the commercial hauler USCSS Nostromo receives an unknown acoustic transmission from LV-426.",
        ),
        TriviaChallenge(
            sector_id="lv426",
            movie_title="Aliens (1986)",
            question="What is the designation of the terraforming colony established on LV-426 before contact was lost?",
            options=["Hadley's Hope", "Tyrell Outpost", "Gateway Station", "Weyland Alpha"],
            correct_index=0,
            explanation="Hadley's Hope was the terraforming colony established in 2157 on LV-426 that fell to the Xenomorph infestation.",
        ),
    ],
    "tannhauser": [
        TriviaChallenge(
            sector_id="tannhauser",
            movie_title="Blade Runner (1982)",
            question="In Roy Batty's famous 'Tears in Rain' soliloquy, what did he watch glitter in the dark near the Tannhäuser Gate?",
            options=["C-beams", "Tachyon flares", "Ion plasma", "Neutron cruisers"],
            correct_index=0,
            explanation="Roy Batty recites: 'I watched C-beams glitter in the dark near the Tannhäuser Gate.'",
        ),
        TriviaChallenge(
            sector_id="tannhauser",
            movie_title="Blade Runner (1982)",
            question="What diagnostic psychological test is administered by Blade Runners to distinguish replicants from humans?",
            options=["Voight-Kampff Test", "Turing-Penrose Probe", "Deckard Index", "Weyland Battery"],
            correct_index=0,
            explanation="The Voight-Kampff machine measures involuntary biological responses such as pupil dilation and capillary blush.",
        ),
    ],
    "zion": [
        TriviaChallenge(
            sector_id="zion",
            movie_title="The Matrix (1999)",
            question="What is the name of Morpheus's hovercraft ship that cruises the underground sewers of the old world?",
            options=["Nebuchadnezzar", "Logos", "Gnosis", "Osiris"],
            correct_index=0,
            explanation="The Nebuchadnezzar is a pirate hovercraft of Zion commanded by Morpheus.",
        ),
        TriviaChallenge(
            sector_id="zion",
            movie_title="The Matrix Reloaded (2003)",
            question="Which program is known as the Architect's counterpart, possessing deep intuitive understanding of human psyche?",
            options=["The Oracle", "The Merovingian", "Persephone", "Seraph"],
            correct_index=0,
            explanation="The Oracle stumbled upon an intuitive solution to Matrix stability through the illusion of choice.",
        ),
    ],
    "solaris": [
        TriviaChallenge(
            sector_id="solaris",
            movie_title="Solaris (1972 / 2002)",
            question="In Andrei Tarkovsky's 'Solaris', what physical phenomenon does the living ocean manifest to psychological visitor Kris Kelvin?",
            options=[
                "His deceased wife Hari",
                "His estranged son",
                "A replica of Earth's moon",
                "A fleet of crystalline entities",
            ],
            correct_index=0,
            explanation="The sentient oceanic entity probes the crew's subconscious minds and materializes Kris Kelvin's late wife, Hari.",
        ),
        TriviaChallenge(
            sector_id="solaris",
            movie_title="2001: A Space Odyssey (1968)",
            question="What is the activation phrase and identity of the cognitive AI aboard Discovery One?",
            options=["HAL 9000", "SAL 9000", "MU-TH-UR 6000", "GERTY 3000"],
            correct_index=0,
            explanation="HAL 9000 (Heuristically Programmed Algorithmic Computer) operates Discovery One's life support and navigation systems.",
        ),
    ],
    "arrakis": [
        TriviaChallenge(
            sector_id="arrakis",
            movie_title="Dune (2021 / 1984)",
            question="What is the native Fremen name for the colossal sandworms inhabiting the dunes of Arrakis?",
            options=["Shai-Hulud", "Kwisatz Haderach", "Muad'Dib", "Crysknife"],
            correct_index=0,
            explanation="Shai-Hulud is revered as the Maker and Old Man of the Desert by the native Fremen.",
        ),
        TriviaChallenge(
            sector_id="arrakis",
            movie_title="Dune (2021)",
            question="Which vital spice substance extends human life, enhances cognitive prescience, and enables interstellar navigation?",
            options=["Melange", "Dilithium", "Kyber", "Substance D"],
            correct_index=0,
            explanation="Melange (the spice) is mined solely on Arrakis and is essential for Spacing Guild Navigators to fold space.",
        ),
    ],
}


class TriviaService:
    def __init__(self):
        self.active_challenges: Dict[str, TriviaChallenge] = {}
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        if self.api_key and genai:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.client = None

    def _generate_dynamic_trivia(self, sector_id: str, movie_context: str) -> Optional[TriviaChallenge]:
        if not self.client:
            return None

        prompt = f"""
        Generate a strictly canonical, factually verified multiple-choice trivia question based on real Sci-Fi movies 
        associated with this theme: '{movie_context}'. Examples: Blade Runner, 2001: A Space Odyssey, Alien, Dune, The Matrix, Solaris, Interstellar.
        Return ONLY valid JSON matching this schema:
        {{
            "movie_title": "Title (Year)",
            "question": "Clear, precise canonical question?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_index": 0,
            "explanation": "Brief explanation of why the answer is canonically correct."
        }}
        Ensure options are non-trivial and exactly one is correct.
        """
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            data = json.loads(response.text)
            options = data["options"]
            if len(options) != 4 or not (0 <= data["correct_index"] <= 3):
                return None
            return TriviaChallenge(
                sector_id=sector_id,
                movie_title=data.get("movie_title", movie_context),
                question=data["question"],
                options=options,
                correct_index=int(data["correct_index"]),
                explanation=data.get("explanation", "Canonical Sci-Fi record verified."),
            )
        except Exception:
            return None

    def get_challenge_for_sector(self, sector_id: str, movie_context: str) -> TriviaChallenge:
        # Attempt Gemini dynamic generation if configured
        challenge = self._generate_dynamic_trivia(sector_id, movie_context)
        if not challenge:
            curated_pool = CURATED_TRIVIA.get(sector_id, CURATED_TRIVIA["lv426"])
            template = random.choice(curated_pool)
            
            # Shuffle options to avoid deterministic index predictability
            indices = list(range(4))
            random.shuffle(indices)
            new_options = [template.options[i] for i in indices]
            new_correct_index = indices.index(template.correct_index)

            challenge = TriviaChallenge(
                sector_id=sector_id,
                movie_title=template.movie_title,
                question=template.question,
                options=new_options,
                correct_index=new_correct_index,
                explanation=template.explanation,
            )

        self.active_challenges[sector_id] = challenge
        return challenge

    def verify_answer(self, sector_id: str, chosen_index: int) -> tuple[bool, str]:
        challenge = self.active_challenges.get(sector_id)
        if not challenge:
            return False, "Combat challenge expired or not found. Re-engage target."
        
        is_correct = (challenge.correct_index == chosen_index)
        explanation = challenge.explanation
        # Clean up challenge once answered
        self.active_challenges.pop(sector_id, None)
        return is_correct, explanation