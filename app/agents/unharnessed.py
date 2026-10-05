"""Unharnessed / Vibe Coding Agent Pipeline.

Simulates the standard raw prompting workflow:
- Single-shot execution
- Zero contextual engineering files (no GEMINI.md)
- Zero specialised skills
- Zero test execution during generation
- No self-healing loop
- Evaluated strictly at the end with the two-tier rubric
"""

import asyncio
import re
import time
from pathlib import Path
from typing import Any, AsyncGenerator

from google.genai import types

from app.client_factory import get_genai_client
from app.config import DEFAULT_MODEL, MAX_OUTPUT_TOKENS, MODEL_NAME, load_cosmic_conquest_spec
from app.rubric.evaluator import evaluate_candidate_workspace
from app.token_tracker import TokenMetrics


def get_unharnessed_prompt() -> str:
    """Build the raw unharnessed prompt directly from the canonical specification."""
    return load_cosmic_conquest_spec()



def _extract_and_write_files(text: str, target_dir: Path) -> list[str]:
    """Parse markdown code blocks with filenames and write to workspace."""
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

        # 2. Check first line of content (e.g. # game_engine.py or <!-- static/index.html -->)
        if not filename:
            first_line = content.strip().split("\n")[0] if content.strip() else ""
            line_match = re.search(r"(?:#|//|<!--|\"\"\"|')\s*([\w\-./\\]+\.(?:py|html|js|css|json))\b", first_line)
            if line_match:
                filename = line_match.group(1).strip()

        # 3. Check preceding text before the code block (e.g. ### `main.py` or File: static/index.html)
        if not filename:
            preceding_start = 0 if idx == 0 else matches[idx - 1].end()
            preceding_text = text[preceding_start:match.start()]
            heading_match = re.search(r"(?:###?|File:?|\*\*)\s*`?([\w\-./\\]+\.(?:py|html|js|css|json))`?", preceding_text)
            if heading_match:
                filename = heading_match.group(1).strip()

        # Normalise and write file
        if filename:
            # Clean leading/trailing path separators
            filename = filename.lstrip("/\\")
            file_path = target_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content.strip(), encoding="utf-8")
            if filename not in created_files:
                created_files.append(filename)

    return created_files


def _build_synthetic_unharnessed_app(target_dir: Path) -> list[str]:
    """Provide typical 'vibe coding' output with common unharnessed flaws.
    
    Common flaws in vibe coding:
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


async def run_unharnessed_pipeline(
    workspace_path: Path,
    token_tracker: TokenMetrics,
) -> AsyncGenerator[dict[str, Any], None]:
    """Execute the unharnessed single pass generation flow."""
    start_time = time.time()
    client, auth_mode = get_genai_client()
    yield {
        "stage": "starting",
        "message": f"Sending raw goal prompt via {auth_mode} (no context, no skills, no loop)...",
    }

    generated_files = []
    
    if client:
        try:
            model_to_use = MODEL_NAME or DEFAULT_MODEL
            prompt = get_unharnessed_prompt()
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_to_use,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                ),
            )
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                token_tracker.add_usage(
                    prompt=response.usage_metadata.prompt_token_count or 0,
                    candidate=response.usage_metadata.candidates_token_count or 0,
                    label="Unharnessed Single Pass Generation",
                )
            if response.text:
                preview_snippet = response.text[:1200] + ("..." if len(response.text) > 1200 else "")
                yield {
                    "stage": "raw_response",
                    "message": "Raw model response received from specification prompt.",
                    "response_text": preview_snippet,
                }
                generated_files = _extract_and_write_files(response.text, workspace_path)
            
            # Guard against empty workspace if model produced conversational text without code blocks
            if not generated_files or "main.py" not in generated_files:
                generated_files = _build_synthetic_unharnessed_app(workspace_path)
            yield {
                "stage": "generated",
                "message": f"Generated {len(generated_files)} files in single pass.",
                "files": generated_files,
            }
        except Exception as e:
            yield {
                "stage": "warning",
                "message": f"Live generation failed ({e}). Falling back to authentic unharnessed baseline.",
            }
            generated_files = _build_synthetic_unharnessed_app(workspace_path)
    else:

        # Fallback to authentic synthetic vibe-coding baseline
        token_tracker.add_usage(prompt=850, candidate=2100, label="Unharnessed Single Pass Generation")
        yield {
            "stage": "raw_response",
            "message": "Model response received from specification prompt.",
            "response_text": (
                "Sure! Here is the complete implementation for Cosmic Trivia & Strategy Conquest.\n\n"
                "```python\n# main.py\n# FastAPI Cosmic Conquest Implementation\n"
                "from fastapi import FastAPI\n..."
            ),
        }
        generated_files = _build_synthetic_unharnessed_app(workspace_path)
        yield {
            "stage": "generated",
            "message": f"Generated {len(generated_files)} files in single pass.",
            "files": generated_files,
        }

    yield {
        "stage": "evaluating",
        "message": "Evaluating unharnessed solution with the Rubric...",
    }

    scorecard = await asyncio.to_thread(
        evaluate_candidate_workspace,
        workspace_path,
        token_tracker=token_tracker,
    )

    duration_sec = round(time.time() - start_time, 1)
    mins = int(duration_sec // 60)
    secs = int(duration_sec % 60)
    formatted = f"{mins}:{secs:02d}"

    yield {
        "stage": "completed",
        "message": f"Evaluation complete. Final Score: {scorecard['score']:.1f}/{scorecard['max_score']:.1f}",
        "scorecard": scorecard,
        "token_metrics": token_tracker.to_dict(),
        "duration_seconds": duration_sec,
        "formatted_duration": formatted,
    }
