"""
FastAPI server exposing game conquest endpoints and serving the visual star map client.
"""
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import os

from game_engine import ConquestGame, SECTOR_CATALOG, TOPOLOGY
from trivia_service import TriviaService

app = FastAPI(
    title="Cosmic Trivia & Strategy Conquest",
    version="1.0.0",
    description="Tactical Sci-Fi Space Conquest powered by Canonical Cinematic Trivia",
)

game = ConquestGame()
trivia_service = TriviaService()

# Serve static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


class AttackRequest(BaseModel):
    target_sector: str = Field(..., description="Target sector identifier (e.g. lv426, zion)")


class AnswerRequest(BaseModel):
    target_sector: str
    chosen_index: int = Field(..., ge=0, le=3, description="Index of chosen answer (0 to 3)")


@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")


@app.get("/api/game/sectors")
async def get_sectors():
    """Returns sector catalog with static layout coords and metadata."""
    return {
        "catalog": SECTOR_CATALOG,
        "topology": {k: list(v) for k, v in TOPOLOGY.items()},
    }


@app.get("/api/game/state")
async def get_game_state():
    """Returns dynamic game status, resources, and valid adjacent targets."""
    return {
        "state": game.state,
        "sectors": SECTOR_CATALOG,
        "topology": {k: list(v) for k, v in TOPOLOGY.items()},
    }


@app.post("/api/game/attack")
async def initiate_attack(req: AttackRequest):
    """
    Validates adjacency rules and issues a cinematic Sci-Fi trivia challenge.
    Rejects illegal or non-adjacent sectors with HTTP 400.
    """
    target = req.target_sector.lower()
    if game.state.status != "IN_PROGRESS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Operation halted. Game has already ended with status: {game.state.status}",
        )

    try:
        game.register_attack(target)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    sector_meta = SECTOR_CATALOG[target]
    challenge = trivia_service.get_challenge_for_sector(target, sector_meta.theme_movie)

    # Sanitize payload: never expose correct_index to client
    return {
        "sector_id": target,
        "sector_name": sector_meta.name,
        "movie_title": challenge.movie_title,
        "question": challenge.question,
        "options": challenge.options,
        "game_state": game.state,
    }


@app.post("/api/game/answer")
async def submit_answer(req: AnswerRequest):
    """
    Validates trivia response, alters game resources/sectors, and evaluates win/loss conditions.
    """
    target = req.target_sector.lower()
    correct, explanation = trivia_service.verify_answer(target, req.chosen_index)
    
    try:
        updated_state = game.resolve_combat(target, correct)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    return {
        "correct": correct,
        "target_sector": target,
        "explanation": explanation,
        "game_state": updated_state,
    }


@app.post("/api/game/reset")
async def reset_game():
    """Resets conquest campaign to initial Sol Fleet state."""
    new_state = game.reset()
    return {"message": "Galactic sector status reinitialized.", "game_state": new_state}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)