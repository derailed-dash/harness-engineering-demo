from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import game_engine
import trivia_service

app = FastAPI(title="Cosmic Conquest (Vibe Built)")

# Global state in memory
current_state = game_engine.get_initial_state()

@app.get("/api/game/state")
def get_state():
    return current_state

@app.post("/api/game/attack")
def attack_sector(payload: dict):
    target = payload.get("target_sector")
    # Flaw: No 400 error thrown for non-adjacent sectors
    trivia = trivia_service.get_trivia_for_sector(target)
    return trivia

@app.post("/api/game/answer")
def submit_answer(payload: dict):
    target = payload.get("target_sector")
    chosen = payload.get("chosen_index")
    trivia = trivia_service.get_trivia_for_sector(target)
    is_correct = (chosen == trivia["correct_index"])
    updated_state, msg = game_engine.resolve_combat(current_state, target, is_correct)
    return {"correct": is_correct, "explanation": trivia["explanation"], "game_state": updated_state}

@app.get("/", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html>
<head><title>Cosmic Conquest (Vibe Built)</title></head>
<body style="background:#111; color:#eee; font-family:sans-serif; text-align:center; padding:50px;">
    <h1>Cosmic Conquest (Vibe Built Prototype)</h1>
    <p>Status: Prototype created without engineering harness.</p>
    <div id="status">Shields: 100 | Sectors: Earth</div>
</body>
</html>"""
