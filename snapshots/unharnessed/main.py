"""
FastAPI Server for Cosmic Trivia & Strategy Conquest.
Exposes REST endpoints and serves the self-contained static UI.
"""
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from game_engine import GameState
from trivia_service import TriviaService

app = FastAPI(title="Cosmic Trivia & Strategy Conquest", version="1.0.0")

# Singleton state instances
game_state = GameState()
trivia_service = TriviaService()

# Serve static asset directory
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class AttackRequest(BaseModel):
    target_sector: str = Field(..., description="ID of adjacent sector to invade")


class AnswerRequest(BaseModel):
    target_sector: str = Field(..., description="Target sector being challenged")
    chosen_index: int = Field(..., ge=0, le=3, description="Selected option index (0 to 3)")


@app.get("/")
async def serve_root():
    """Serves the main interactive conquest UI."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend template not found.")
    return FileResponse(index_file)


@app.get("/api/game/state")
async def get_state():
    """Returns current star fleet and galaxy conquest status."""
    return game_state.to_dict()


@app.post("/api/game/attack")
async def attack_sector(payload: AttackRequest):
    """
    Validates star map adjacency and initiates a trivia combat encounter.
    Returns the trivia challenge without leaking the correct answer index.
    """
    can_attack, message = game_state.can_attack(payload.target_sector)
    if not can_attack:
        raise HTTPException(status_code=400, detail=message)

    challenge = trivia_service.generate_challenge(payload.target_sector)
    # Stash challenge server-side for secure resolution
    game_state.active_challenge = {
        "target_sector": payload.target_sector,
        "movie_title": challenge["movie_title"],
        "question": challenge["question"],
        "options": challenge["options"],
        "correct_index": challenge["correct_index"],
        "explanation": challenge["explanation"]
    }

    # Transmit challenge payload stripped of answer index
    return {
        "target_sector": payload.target_sector,
        "movie_title": challenge["movie_title"],
        "question": challenge["question"],
        "options": challenge["options"]
    }


@app.post("/api/game/answer")
async def answer_challenge(payload: AnswerRequest):
    """
    Validates player answer choice, resolves combat, and returns updated state.
    """
    active = game_state.active_challenge
    if not active:
        raise HTTPException(
            status_code=400,
            detail="No active combat challenge found. Please select a valid adjacent sector to attack."
        )

    if active["target_sector"] != payload.target_sector:
        raise HTTPException(
            status_code=400,
            detail=f"Sector mismatch: combat underway at '{active['target_sector']}', not '{payload.target_sector}'."
        )

    correct_index = active["correct_index"]
    is_correct = (payload.chosen_index == correct_index)
    explanation = active["explanation"]

    combat_summary = game_state.resolve_combat(payload.target_sector, is_correct)

    return {
        "correct": is_correct,
        "correct_index": correct_index,
        "explanation": explanation,
        "combat_summary": combat_summary,
        "game_state": game_state.to_dict()
    }


@app.post("/api/game/reset")
async def reset_game():
    """Resets galaxy conquest back to Earth initial state."""
    global game_state
    game_state = GameState()
    return {
        "message": "Sol Fleet re-initialized at Earth Capital.",
        "game_state": game_state.to_dict()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)