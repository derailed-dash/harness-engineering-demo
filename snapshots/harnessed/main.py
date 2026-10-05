"""FastAPI HTTP Application routing Cosmic Conquest gameplay.

Architectural Intent:
Exposes REST endpoints with strict Pydantic validation, enforcing graph adjacency rules
and returning HTTP 400 with actionable feedback on invalid attacks.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

import game_engine
import trivia_service

app = FastAPI(title="Cosmic Trivia & Strategy Conquest")

# Global session game state
state = game_engine.get_initial_state()

class AttackRequest(BaseModel):
    target_sector: str = Field(..., description="Target sector identifier to attack")

class AnswerRequest(BaseModel):
    target_sector: str = Field(..., description="Target sector identifier")
    chosen_index: int = Field(..., ge=0, le=3, description="0-indexed multiple choice selection")

@app.get("/api/game/state")
def get_state() -> dict:
    """Return full state including currently attackable adjacent sectors."""
    result = dict(state)
    result["available_targets"] = game_engine.get_available_targets(state)
    return result

@app.post("/api/game/attack")
def attack_sector(req: AttackRequest) -> dict:
    """Initiate attack on an adjacent sector, returning trivia challenge."""
    if not game_engine.can_attack_sector(state, req.target_sector):
        raise HTTPException(
            status_code=400,
            detail=f"Sector '{req.target_sector}' is not adjacent to controlled territory. Valid targets: {game_engine.get_available_targets(state)}",
        )
    return trivia_service.get_trivia_for_sector(req.target_sector)

@app.post("/api/game/answer")
def submit_answer(req: AnswerRequest) -> dict:
    """Evaluate trivia answer and advance game state."""
    trivia = trivia_service.get_trivia_for_sector(req.target_sector)
    is_correct = (req.chosen_index == trivia["correct_index"])
    updated_state, msg = game_engine.resolve_combat(state, req.target_sector, is_correct)
    return {
        "correct": is_correct,
        "explanation": trivia["explanation"],
        "message": msg,
        "game_state": updated_state,
    }

@app.post("/api/game/reset")
def reset_game() -> dict:
    """Reset game to pristine state."""
    global state
    state = game_engine.get_initial_state()
    return {"message": "Game reset successfully", "game_state": state}

# Serve static UI
static_dir = Path(__file__).parent / "static"
if (static_dir / "index.html").exists():
    @app.get("/", response_class=HTMLResponse)
    def index():
        return (static_dir / "index.html").read_text(encoding="utf-8")
