"""
FastAPI Application Entry Point for Cosmic Trivia & Strategy Conquest.
Exposes RESTful endpoints for game state, sector attacks, trivia verification, and resets.
Serves interactive front-end assets.
"""

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from game_engine import CosmicGameEngine, SECTOR_METADATA, PendingChallenge
from trivia_service import TriviaService

app = FastAPI(
    title="Cosmic Trivia & Strategy Conquest",
    description="Tactical Sci-Fi Star Map Conquest powered by cinematic trivia.",
    version="1.0.0"
)

# Instantiate singleton game engine and trivia service
engine = CosmicGameEngine()
trivia_service = TriviaService()

# Request Models
class AttackRequest(BaseModel):
    target_sector: str = Field(..., description="Target sector id (e.g., 'lv426', 'zion')")

class AnswerRequest(BaseModel):
    target_sector: str = Field(..., description="Target sector id where combat is pending")
    chosen_index: int = Field(..., ge=0, le=3, description="Index of chosen answer (0 to 3)")


@app.get("/api/game/sectors")
def get_sectors():
    """Returns static galaxy metadata including map positions and film inspirations."""
    return SECTOR_METADATA


@app.get("/api/game/state")
def get_game_state():
    """Returns full current state of the conquest and player fleet."""
    return engine.get_serializable_state()


@app.post("/api/game/attack")
def initiate_attack(req: AttackRequest):
    """
    Validates attack target according to star map graph adjacency.
    If valid, triggers the Gatekeeper trivia challenge.
    """
    target = req.target_sector.strip().lower()

    # Verify target legitimacy & adjacency
    err = engine.validate_attack(target)
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    # Fetch sector metadata
    meta = SECTOR_METADATA[target]

    # Generate trivia grounded in authentic sci-fi
    trivia_data = trivia_service.get_trivia_for_sector(
        sector_id=target,
        sector_theme=meta["theme"],
        film_hint=meta["film_universe"]
    )

    # Register challenge in game state
    challenge = PendingChallenge(
        target_sector=target,
        question=trivia_data["question"],
        options=trivia_data["options"],
        correct_index=trivia_data["correct_index"],
        movie_title=trivia_data["movie_title"],
        explanation=trivia_data["explanation"]
    )
    engine.register_challenge(challenge)

    # Return challenge payload without revealing correct index
    return {
        "target_sector": target,
        "sector_name": meta["name"],
        "film_universe": meta["film_universe"],
        "movie_title": challenge.movie_title,
        "question": challenge.question,
        "options": challenge.options
    }


@app.post("/api/game/answer")
def submit_answer(req: AnswerRequest):
    """
    Evaluates player's chosen trivia answer, resolves shields/energy, and updates sector control.
    """
    target = req.target_sector.strip().lower()

    if not engine.state.pending_challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending battle challenge found. Please select an adjacent sector to attack."
        )

    if engine.state.pending_challenge.target_sector != target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target mismatch: Active challenge is on sector '{engine.state.pending_challenge.target_sector}', not '{target}'."
        )

    try:
        result = engine.resolve_answer(req.chosen_index)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/api/game/reset")
def reset_game():
    """Resets the galaxy to pristine initial conditions."""
    new_state = engine.reset()
    return engine.get_serializable_state()


# Mount static assets
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="UI frontend template not found.")
    return FileResponse(str(index_file))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)