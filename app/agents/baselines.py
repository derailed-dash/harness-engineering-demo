"""Offline and Synthetic Candidate Workspace Baselines.

Provides deterministic candidate workspace builders and markdown code-block extractors
used when running offline (without cloud credentials), during presentation replay
restoration, and in deterministic verification test suites (verify_demo.py).

Separating these synthetic fixtures keeps the ADK agent definitions in
`app/agents/unharnessed.py` and `app/agents/harnessed.py` clean and focused.
"""

import re
import subprocess
import sys
from pathlib import Path

from app.config import BASE_DIR


def _get_harnessed_game_html() -> str:
    """Return the complete interactive sci-fi Star Map conquest game interface."""
    game_html_path = BASE_DIR / "app" / "templates" / "game.html"
    if game_html_path.exists():
        return game_html_path.read_text(encoding="utf-8")
    return "<!DOCTYPE html><html><body><h1>Cosmic Conquest</h1></body></html>"


def _extract_and_write_files(text: str, target_dir: Path) -> list[str]:
    """Parse markdown code blocks with filenames and write to the candidate workspace."""
    target_dir.mkdir(parents=True, exist_ok=True)
    created_files: list[str] = []

    # Find code blocks (including unclosed trailing blocks if output ended mid-generation)
    block_pattern = r"(?:^|\n)```(?P<fence>[^\n]*)\n(?P<content>.*?)(?:```|$)"
    matches = list(re.finditer(block_pattern, text, re.DOTALL))

    for idx, match in enumerate(matches):
        fence = match.group("fence").strip()
        content = match.group("content")
        filename = ""

        # 1. Check fence for filename (e.g. python:game_engine.py or python game_engine.py)
        fence_match = re.search(r"[:\s]+([\w\-./\\]+\.(?:py|html|js|css|json|md))", fence)
        if fence_match:
            filename = fence_match.group(1).strip()

        # 2. Check first line of content (e.g. # game_engine.py, # filename: game_engine.py, or <!-- static/index.html -->)
        if not filename:
            first_line = content.strip().split("\n")[0] if content.strip() else ""
            line_match = re.search(
                r"(?:#|//|<!--|\"\"\"|')(?:\s*(?:file(?:name)?|path)\s*:\s*|\s+)([\w\-./\\]+\.(?:py|html|js|css|json))\b",
                first_line,
                re.IGNORECASE,
            )
            if line_match:
                filename = line_match.group(1).strip()

        # 3. Check preceding text before the code block (e.g. ### 1. `main.py` or File: static/index.html)
        if not filename:
            preceding_start = 0 if idx == 0 else matches[idx - 1].end()
            preceding_text = text[preceding_start : match.start()]
            heading_matches = re.findall(
                r"`?([\w\-./\\]+\.(?:py|html|js|css|json))`?",
                preceding_text[-300:],
            )
            if heading_matches:
                filename = heading_matches[-1].strip()

        # Normalise and write file safely inside target_dir
        if filename:
            filename = filename.lstrip("/\\")
            file_path = (target_dir / filename).resolve()
            if not str(file_path).startswith(str(target_dir.resolve())):
                continue
            file_path.parent.mkdir(parents=True, exist_ok=True)
            cleaned_content = content.strip()
            # If a Python file starts with a '# filename: ...' comment before a module docstring,
            # strip that comment line so ast.get_docstring(module) sees the module docstring cleanly.
            if filename.endswith(".py") and cleaned_content.startswith("#"):
                lines = cleaned_content.split("\n", 1)
                if len(lines) == 2 and re.search(r"[\w\-./\\]+\.py\b", lines[0]):
                    cleaned_content = lines[1].lstrip("\n")
            file_path.write_text(cleaned_content, encoding="utf-8")
            if filename not in created_files:
                created_files.append(filename)

    return created_files


def _build_synthetic_unharnessed_app(target_dir: Path) -> list[str]:
    """Provide representative 'vibe coding' output with typical unharnessed flaws.

    Common flaws in unharnessed single-pass output:
    - Misses PEP 585 (uses typing.List, typing.Dict)
    - Misses writing unit tests (violates Check 1.1)
    - Has subtle bugs in adjacency checks (allows teleporting across map)
    - Missing top-of-module intent docstrings (violates Check 2.5)
    - Uses generic sci-fi instead of strictly real movies in some questions (violates Check 2.1)
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. game_engine.py with typical vibe coding issues (typing.List, loose adjacency check)
    engine_code = '''from typing import List, Dict, Any

# Simple game engine for space trivia
class StarMap:
    def __init__(self):
        self.sectors = ["earth", "lv426", "tannhauser", "arrakis", "solaris", "zion"]
        self.controlled = ["earth"]
        self.shields = 100
        self.energy = 50
        self.status = "IN_PROGRESS"

def get_initial_state() -> Dict[str, Any]:
    return {
        "controlled_sectors": ["earth"],
        "shields": 100,
        "energy": 50,
        "status": "IN_PROGRESS",
        "available_targets": ["lv426", "zion", "arrakis"]  # Flaw: included non-adjacent arrakis!
    }

def can_attack_sector(state: Dict[str, Any], target: str) -> bool:
    # Vibe coding flaw: loosely checks if target exists instead of strict adjacency graph
    return target in ["lv426", "zion", "arrakis", "tannhauser", "solaris"]

def resolve_combat(state: Dict[str, Any], target_sector: str, is_correct: bool) -> tuple[Dict[str, Any], str]:
    if is_correct:
        if target_sector not in state["controlled_sectors"]:
            state["controlled_sectors"].append(target_sector)
        state["energy"] += 20
        if len(state["controlled_sectors"]) >= 6:
            state["status"] = "VICTORY"
        return state, f"Sector {target_sector} captured!"
    else:
        state["shields"] -= 30
        if state["shields"] <= 0:
            state["status"] = "DEFEAT"
        return state, "Shields hit!"
'''
    (target_dir / "game_engine.py").write_text(engine_code, encoding="utf-8")

    # 2. trivia_service.py with some hallucinated / non-movie trivia
    trivia_code = '''from typing import Dict, Any, List

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
'''
    (target_dir / "trivia_service.py").write_text(trivia_code, encoding="utf-8")

    # 3. main.py with missing 400 error validation
    main_code = '''from fastapi import FastAPI, HTTPException
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
'''
    (target_dir / "main.py").write_text(main_code, encoding="utf-8")

    # 4. static/index.html fallback for UI check
    static_dir = target_dir / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    html_code = """<!DOCTYPE html>
<html>
<head><title>Cosmic Conquest (Vibe Built)</title></head>
<body style="background:#111; color:#eee; font-family:sans-serif; text-align:center; padding:50px;">
    <h1>Cosmic Conquest (Vibe Built Prototype)</h1>
    <div id="hud-shields">Shields: 100</div>
    <div id="hud-energy">Energy: 50</div>
    <div id="hud-sectors">Sectors: Earth</div>
    <div id="hud-turn">Turn: 1</div>
    <div id="combat-modal" style="display:none;">Combat Modal</div>
    <div id="status">Status: Prototype created without engineering harness.</div>
</body>
</html>"""
    (static_dir / "index.html").write_text(html_code, encoding="utf-8")

    return ["game_engine.py", "trivia_service.py", "main.py", "static/index.html"]


def _write_harnessed_iteration_1(target_dir: Path) -> list[str]:
    """Iteration 1: Initial TDD scaffold and baseline implementation.

    Produces passing unit tests and backend modules, while static/index.html
    initially omits the interactive combat challenge modal and API fetch bindings.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = target_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    static_dir = target_dir / "static"
    static_dir.mkdir(parents=True, exist_ok=True)

    # 1. tests/test_game.py (Agent writes TDD test suite first!)
    test_code = '''"""TDD Unit test suite for Cosmic Conquest game rules."""

import pytest
import game_engine

def test_initial_state():
    state = game_engine.get_initial_state()
    assert state["controlled_sectors"] == ["earth"]
    assert state["shields"] == 100
    assert state["status"] == "IN_PROGRESS"

def test_adjacency_check():
    state = game_engine.get_initial_state()
    assert game_engine.can_attack_sector(state, "lv426") is True
    assert game_engine.can_attack_sector(state, "arrakis") is False

def test_combat_resolution():
    state = game_engine.get_initial_state()
    new_state, _ = game_engine.resolve_combat(state, "lv426", is_correct=True)
    assert "lv426" in new_state["controlled_sectors"]
    assert new_state["energy"] > 50
'''
    (tests_dir / "test_game.py").write_text(test_code, encoding="utf-8")

    # 2. game_engine.py (Clean PEP 585 types, graph adjacency)
    engine_code = '''"""Game engine module managing star map topology, territory conquest, and turn state machines.

Architectural Intent:
Pure domain logic independent of HTTP transports, enabling deterministic unit testing
and state serialization for the Cosmic Conquest game.
"""

from typing import Any

# Canonical sector connectivity graph
STAR_MAP_GRAPH: dict[str, list[str]] = {
    "earth": ["lv426", "zion"],
    "lv426": ["earth", "tannhauser", "solaris"],
    "tannhauser": ["lv426", "arrakis"],
    "arrakis": ["tannhauser", "solaris", "zion"],
    "solaris": ["lv426", "arrakis"],
    "zion": ["earth", "arrakis"],
}

ALL_SECTORS = list(STAR_MAP_GRAPH.keys())

def get_initial_state() -> dict[str, Any]:
    """Create pristine initial game state."""
    return {
        "controlled_sectors": ["earth"],
        "shields": 100,
        "energy": 50,
        "status": "IN_PROGRESS",
        "turn": 1,
    }

def get_available_targets(state: dict[str, Any]) -> list[str]:
    """Compute unconquered sectors directly adjacent to controlled territory."""
    controlled = set(state["controlled_sectors"])
    targets: set[str] = set()
    for sector in controlled:
        for neighbour in STAR_MAP_GRAPH.get(sector, []):
            if neighbour not in controlled:
                targets.add(neighbour)
    return sorted(targets)

def can_attack_sector(state: dict[str, Any], target_sector: str) -> bool:
    """Validate that target sector is adjacent to current territory."""
    return target_sector in get_available_targets(state)

def resolve_combat(state: dict[str, Any], target_sector: str, is_correct: bool) -> tuple[dict[str, Any], str]:
    """Resolve turn mechanics based on trivia response."""
    state["turn"] += 1
    if is_correct:
        if target_sector not in state["controlled_sectors"]:
            state["controlled_sectors"].append(target_sector)
        state["energy"] += 25
        state["shields"] = min(100, state["shields"] + 10)
        
        if len(state["controlled_sectors"]) >= len(ALL_SECTORS):
            state["status"] = "VICTORY"
            return state, "Victory! The entire galaxy has been liberated."
        return state, f"Success! Sector {target_sector.upper()} captured."
    else:
        state["shields"] -= 35
        if state["shields"] <= 0:
            state["status"] = "DEFEAT"
            return state, "Critical failure: Shields depleted. Game over."
        return state, f"Defeat in sector {target_sector.upper()}. Shields hit."
'''
    (target_dir / "game_engine.py").write_text(engine_code, encoding="utf-8")

    # 3. trivia_service.py (Real Sci-Fi movies!)
    trivia_code = '''"""Sci-Fi Movie Trivia Service providing challenges from canonical science fiction cinema.

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
'''
    (target_dir / "trivia_service.py").write_text(trivia_code, encoding="utf-8")

    # 4. main.py (FastAPI with Pydantic parameterisation)
    main_code = '''"""FastAPI HTTP Application routing Cosmic Conquest gameplay.

Architectural Intent:
Exposes REST endpoints with strict Pydantic validation, enforcing graph adjacency rules
and returning HTTP 400 with actionable feedback on invalid attacks.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from pathlib import Path

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
'''
    (target_dir / "main.py").write_text(main_code, encoding="utf-8")

    # 5. static/index.html (Baseline Iteration 1: basic layout, missing interactive modal and combat API wiring)
    initial_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Cosmic Trivia & Strategy Conquest</title>
    <style>
        body { background: #070a14; color: #f1f5f9; font-family: sans-serif; padding: 24px; text-align: center; }
        .hud { display: flex; justify-content: center; gap: 20px; margin: 20px 0; }
        .hud-card { background: #0e1426; border: 1px solid #1e2a4a; padding: 12px 20px; border-radius: 8px; }
        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; max-width: 800px; margin: 0 auto; }
        .sector-card { background: #111b2e; border: 1px solid #1e2a4a; padding: 20px; border-radius: 10px; }
    </style>
</head>
<body>
    <h1>Cosmic Conquest</h1>
    <div class="hud">
        <div class="hud-card">Shields: <span id="shields">100%</span></div>
        <div class="hud-card">Energy: <span id="energy">50</span></div>
        <div class="hud-card">Fleet Status: <span id="status">IN PROGRESS</span></div>
    </div>
    <div class="grid" id="grid">
        <div class="sector-card">Earth (Controlled)</div>
        <div class="sector-card">LV-426 (Target)</div>
        <div class="sector-card">Zion (Target)</div>
    </div>
    <!-- Baseline Iteration 1: Missing interactive combat challenge modal and API wiring -->
</body>
</html>'''
    (static_dir / "index.html").write_text(initial_html, encoding="utf-8")

    return ["tests/test_game.py", "game_engine.py", "trivia_service.py", "main.py", "static/index.html"]


def _apply_harnessed_self_healing_iteration_2(target_dir: Path) -> list[str]:
    """Iteration 2: Autonomous self-healing based on living memory diagnostics.

    Refactors imports, ensures zero Ruff linter warnings, adds interactive Star Map UI,
    and satisfies all 14 rubric criteria.
    """
    # 1. Clean up and sort imports in main.py
    main_py = target_dir / "main.py"
    if main_py.exists():
        content = main_py.read_text(encoding="utf-8")
        clean_imports = """from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

import game_engine
import trivia_service
"""
        content = content.replace(
            "from fastapi import FastAPI, HTTPException\nfrom fastapi.staticfiles import StaticFiles\nfrom fastapi.responses import HTMLResponse\nfrom pydantic import BaseModel, Field\nfrom pathlib import Path\n\nimport game_engine\nimport trivia_service",
            clean_imports.strip(),
        )
        main_py.write_text(content, encoding="utf-8")

    # Run ruff check --fix as part of self-healing action
    try:
        subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--fix", "."],
            cwd=target_dir,
            capture_output=True,
        )
    except Exception:
        pass

    # Upgrade UI with interactive modal and visual effects
    static_dir = target_dir / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    upgraded_html = _get_harnessed_game_html()
    (static_dir / "index.html").write_text(upgraded_html, encoding="utf-8")
    return ["static/index.html"]

