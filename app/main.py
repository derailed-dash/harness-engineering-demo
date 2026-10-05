"""Harness Engineering Workbench - FastAPI Web Server.

Serves the presentation workbench, SSE event streams for live & replay comparisons,
and mounts interactive preview endpoints for both generated Sci-Fi games.
"""

import json
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.client_factory import get_genai_client
from app.config import (
    BASE_DIR,
    DEFAULT_MODEL,
    HARNESSED_DIR,
    HOST,
    MODEL_NAME,
    PORT,
    UNHARNESSED_DIR,
    load_cosmic_conquest_spec,
    load_harness_context,
    load_harness_skills,
)
from app.orchestrator import DemoOrchestrator
from app.replay.player import stream_replay_events

app = FastAPI(title="Harness Engineering Workbench")

# Mount static assets and templates
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

orchestrator = DemoOrchestrator()


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> Any:
    """Render the primary split-screen comparison workbench."""
    _, auth_mode = get_genai_client()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "model_name": MODEL_NAME or DEFAULT_MODEL,
            "auth_mode": auth_mode,
            "spec_content": load_cosmic_conquest_spec(),
            "harness_context_content": load_harness_context(),
            "harness_skills": load_harness_skills(),
        },
    )



@app.get("/api/status")
def get_status() -> dict[str, Any]:
    """Return runtime status and configuration."""
    _, auth_mode = get_genai_client()
    return {
        "status": "online",
        "model": MODEL_NAME or DEFAULT_MODEL,
        "auth_mode": auth_mode,
        "is_running": orchestrator.is_running,
    }


@app.post("/api/reset")
def reset_workspaces() -> dict[str, Any]:
    """Reset workspaces, clean generated code (preserving READMEs), and zero counters."""
    global _unharnessed_game_instance, _harnessed_game_state
    _unharnessed_game_instance = None
    _harnessed_game_state = None
    _purge_candidate_modules()
    summary = orchestrator.reset_workspaces()
    return {
        "status": "ok",
        "message": f"Cleaned {summary['total_cleaned']} generated items across candidate workspaces.",
        "summary": summary,
    }


@app.get("/api/spec")
def get_spec() -> dict[str, Any]:
    """Return the raw markdown content and metadata for the shared goal specification."""
    content = load_cosmic_conquest_spec()
    return {
        "filename": "specs/cosmic_conquest_spec.md",
        "title": "Cosmic Trivia & Strategy Conquest Specification",
        "content": content,
    }


@app.get("/api/harness-context")
def get_harness_context() -> dict[str, Any]:
    """Return the raw markdown content and metadata for the harness engineering context."""
    content = load_harness_context()
    return {
        "filename": "harness/harness_context.md",
        "title": "Engineering Context & Harness Guardrails (GEMINI.md)",
        "content": content,
    }



@app.get("/api/skills")
def get_skills() -> dict[str, Any]:
    """Return all available specialised harness skills."""
    skills = load_harness_skills()
    return {
        "count": len(skills),
        "skills": list(skills.keys()),
    }


@app.get("/api/skills/{skill_name}")
def get_skill(skill_name: str) -> dict[str, Any]:
    """Return raw markdown content and metadata for a specific specialised skill."""
    skills = load_harness_skills()
    if skill_name not in skills:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found.")
    return {
        "skill": skill_name,
        "filename": f"harness/skills/{skill_name}/SKILL.md",
        "content": skills[skill_name],
    }


@app.get("/api/stream/compare")

async def stream_live_compare():
    """SSE endpoint for live model execution."""
    async def event_generator():
        async for event in orchestrator.stream_comparison():
            payload = json.dumps(event)
            yield f"data: {payload}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.get("/api/stream/replay")
async def stream_presentation_replay():
    """SSE endpoint for zero-latency presentation replay."""
    async def event_generator():
        async for event in stream_replay_events():
            payload = json.dumps(event)
            yield f"data: {payload}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ============================================================================
# Dynamic In-Process Previews for Generated Applications
# ============================================================================

_CANDIDATE_BARE_MODULES = {"main", "game_engine", "trivia_service"}
_current_active_preview_workspace: str | None = None


def _purge_candidate_modules() -> None:
    """Purge all cached candidate modules from sys.modules across both workspaces."""
    global _current_active_preview_workspace
    _current_active_preview_workspace = None
    for k in list(sys.modules.keys()):
        if k in _CANDIDATE_BARE_MODULES or k.startswith("candidate_") or k.startswith("workspace_"):
            del sys.modules[k]


def _get_workspace_module(workspace: Path, module_name: str) -> Any:
    """Safely and independently load a module from an isolated candidate workspace."""
    import importlib.util
    global _current_active_preview_workspace

    # Switching workspaces: purge bare module names to guarantee zero cross-workspace bleed
    if _current_active_preview_workspace != workspace.name:
        for k in _CANDIDATE_BARE_MODULES:
            if k in sys.modules:
                del sys.modules[k]
        _current_active_preview_workspace = workspace.name

    file_path = workspace / f"{module_name}.py"
    if not file_path.exists():
        raise FileNotFoundError(f"Module {module_name}.py not found in {workspace}")

    unique_mod_name = f"candidate_{workspace.name}_{module_name}"
    str_path = str(file_path.parent.resolve())
    sys_path_saved = list(sys.path)
    if str_path in sys.path:
        sys.path.remove(str_path)
    sys.path.insert(0, str_path)

    try:
        spec = importlib.util.spec_from_file_location(unique_mod_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module spec for {file_path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[unique_mod_name] = mod
        # Ensure intra-workspace imports resolve to this workspace module
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path = sys_path_saved



# --- Unharnessed Game Preview Routes ---

@app.get("/preview/unharnessed", response_class=HTMLResponse)
async def preview_unharnessed_ui():
    """Serve the unharnessed prototype UI."""
    html_file = UNHARNESSED_DIR / "static" / "index.html"
    no_cache_headers = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
    if not html_file.exists():
        return HTMLResponse(
            """<!DOCTYPE html><html><body style="background:#0a0c16;color:#e0e6ed;font-family:sans-serif;padding:60px 20px;text-align:center;">
            <h2>Unharnessed Workspace Preview</h2>
            <p style="color:#ff3366;font-size:1.05rem;margin-top:10px;">Status: Awaiting generation run.</p>
            <p style="color:#94a3b8;font-size:0.9rem;margin-top:6px;">Click <strong>'Run Comparison'</strong> or <strong>'Presentation Replay'</strong> in the header to build and inspect this workspace.</p>
            </body></html>""",
            headers=no_cache_headers,
        )
    content = html_file.read_text(encoding="utf-8")
    # Patch API paths to point to /preview/unharnessed/api/
    patched = content.replace("'/api/", "'/preview/unharnessed/api/").replace('"/api/', '"/preview/unharnessed/api/')
    return HTMLResponse(patched, headers=no_cache_headers)


# In-memory unharnessed game state instance if candidate uses GameState class
_unharnessed_game_instance: Any = None


def _get_unharnessed_state_dict() -> dict[str, Any]:
    global _unharnessed_game_instance
    mod = _get_workspace_module(UNHARNESSED_DIR, "game_engine")
    if hasattr(mod, "get_initial_state"):
        return mod.get_initial_state()
    if hasattr(mod, "GameState"):
        if _unharnessed_game_instance is None:
            _unharnessed_game_instance = mod.GameState()
        return _unharnessed_game_instance.to_dict()
    if hasattr(mod, "game") and hasattr(mod.game, "to_dict"):
        return mod.game.to_dict()
    raise RuntimeError("Candidate game_engine exposes neither get_initial_state nor GameState")


@app.get("/preview/unharnessed/api/game/state")
async def unharnessed_api_state():
    try:
        return _get_unharnessed_state_dict()
    except Exception as e:
        return {"error": str(e), "controlled_sectors": ["earth"], "shields": 100, "energy": 50, "status": "ERROR"}


@app.post("/preview/unharnessed/api/game/attack")
async def unharnessed_api_attack(req: Request):
    try:
        body = await req.json()
        target = body.get("target_sector", "lv426")
        mod = _get_workspace_module(UNHARNESSED_DIR, "trivia_service")
        if hasattr(mod, "get_trivia_for_sector"):
            return mod.get_trivia_for_sector(target)
        if hasattr(mod, "trivia_service"):
            g_mod = _get_workspace_module(UNHARNESSED_DIR, "game_engine")
            sector_info = getattr(g_mod, "SECTORS_METADATA", {}).get(target, {"name": target, "sci_fi_theme": "Sci-Fi"})
            ts = mod.trivia_service
            if hasattr(ts, "get_challenge_for_sector"):
                return ts.get_challenge_for_sector(target, sector_info)
            if hasattr(ts, "get_trivia_for_sector"):
                return ts.get_trivia_for_sector(target)
        return {"error": "Trivia service not found"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/preview/unharnessed/api/game/answer")
async def unharnessed_api_answer(req: Request):
    global _unharnessed_game_instance
    try:
        body = await req.json()
        target = body.get("target_sector", "lv426")
        chosen = body.get("chosen_index", 0)
        t_mod = _get_workspace_module(UNHARNESSED_DIR, "trivia_service")
        g_mod = _get_workspace_module(UNHARNESSED_DIR, "game_engine")

        if _unharnessed_game_instance is not None and hasattr(_unharnessed_game_instance, "resolve_answer"):
            res = _unharnessed_game_instance.resolve_answer(chosen)
            return {
                "correct": res.get("correct", False),
                "explanation": res.get("explanation", ""),
                "game_state": _unharnessed_game_instance.to_dict(),
                "battle_result": res,
            }

        trivia = t_mod.get_trivia_for_sector(target) if hasattr(t_mod, "get_trivia_for_sector") else {}
        is_correct = (chosen == trivia.get("correct_index", 0))
        if hasattr(g_mod, "get_initial_state"):
            state = g_mod.get_initial_state()
            updated, _ = g_mod.resolve_combat(state, target, is_correct)
            return {"correct": is_correct, "explanation": trivia.get("explanation", ""), "game_state": updated}
        return {"correct": is_correct, "explanation": "", "game_state": {}}
    except Exception as e:
        return {"error": str(e)}



# --- Harnessed Game Preview Routes ---

@app.get("/preview/harnessed", response_class=HTMLResponse)
async def preview_harnessed_ui():
    """Serve the harnessed verified game UI."""
    html_file = HARNESSED_DIR / "static" / "index.html"
    no_cache_headers = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
    if not html_file.exists():
        return HTMLResponse(
            """<!DOCTYPE html><html><body style="background:#0a0c16;color:#e0e6ed;font-family:sans-serif;padding:60px 20px;text-align:center;">
            <h2>Harnessed Workspace Preview</h2>
            <p style="color:#00ffcc;font-size:1.05rem;margin-top:10px;">Status: Awaiting harness loop run.</p>
            <p style="color:#94a3b8;font-size:0.9rem;margin-top:6px;">Click <strong>'Run Comparison'</strong> or <strong>'Presentation Replay'</strong> in the header to build and test this workspace.</p>
            </body></html>""",
            headers=no_cache_headers,
        )
    content = html_file.read_text(encoding="utf-8")
    # Patch API paths to point to /preview/harnessed/api/
    patched = content.replace("'/api/", "'/preview/harnessed/api/").replace('"/api/', '"/preview/harnessed/api/')
    return HTMLResponse(patched, headers=no_cache_headers)


# Persistent in-memory session state for previewing the harnessed game
_harnessed_game_state: dict[str, Any] | None = None

def _get_harnessed_state() -> dict[str, Any]:
    global _harnessed_game_state
    if _harnessed_game_state is None:
        try:
            g_mod = _get_workspace_module(HARNESSED_DIR, "game_engine")
            _harnessed_game_state = g_mod.get_initial_state()
        except Exception:
            _harnessed_game_state = {"controlled_sectors": ["earth"], "shields": 100, "energy": 50, "status": "IN_PROGRESS", "turn": 1}
    assert _harnessed_game_state is not None
    return _harnessed_game_state


@app.get("/preview/harnessed/api/game/state")
async def harnessed_api_state():
    try:
        g_mod = _get_workspace_module(HARNESSED_DIR, "game_engine")
        state = _get_harnessed_state()
        result = dict(state)
        result["available_targets"] = g_mod.get_available_targets(state)
        return result
    except Exception as e:
        return {"error": str(e), "controlled_sectors": ["earth"], "shields": 100, "energy": 50, "status": "ERROR"}


@app.post("/preview/harnessed/api/game/attack")
async def harnessed_api_attack(req: Request):
    try:
        body = await req.json()
        target = (body.get("target_sector") or "").lower()
        g_mod = _get_workspace_module(HARNESSED_DIR, "game_engine")
        t_mod = _get_workspace_module(HARNESSED_DIR, "trivia_service")
        state = _get_harnessed_state()
        if not g_mod.can_attack_sector(state, target):
            raise HTTPException(status_code=400, detail=f"Sector {target} is not adjacent to controlled territory.")
        if hasattr(t_mod, "get_trivia_for_sector"):
            return t_mod.get_trivia_for_sector(target)
        if hasattr(t_mod, "TriviaService"):
            ts = t_mod.TriviaService()
            if hasattr(ts, "get_trivia_for_sector"):
                return ts.get_trivia_for_sector(target)
            if hasattr(ts, "generate_challenge"):
                return ts.generate_challenge(target)
        raise RuntimeError("Trivia service module does not expose get_trivia_for_sector or TriviaService")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Combat initialisation error: {e}")


@app.post("/preview/harnessed/api/game/answer")
async def harnessed_api_answer(req: Request):
    try:
        body = await req.json()
        target = (body.get("target_sector") or "").lower()
        chosen = body.get("chosen_index")
        g_mod = _get_workspace_module(HARNESSED_DIR, "game_engine")
        t_mod = _get_workspace_module(HARNESSED_DIR, "trivia_service")
        state = _get_harnessed_state()
        trivia = (
            t_mod.get_trivia_for_sector(target)
            if hasattr(t_mod, "get_trivia_for_sector")
            else (
                t_mod.TriviaService().get_trivia_for_sector(target)
                if hasattr(t_mod, "TriviaService")
                else {}
            )
        )
        correct_idx = trivia.get("correct_index", 0) if isinstance(trivia, dict) else getattr(trivia, "correct_index", 0)
        is_correct = (chosen == correct_idx)
        updated_state, msg = g_mod.resolve_combat(state, target, is_correct)
        explanation = trivia.get("explanation", "") if isinstance(trivia, dict) else getattr(trivia, "explanation", "")
        return {
            "correct": is_correct,
            "explanation": explanation,
            "message": msg,
            "game_state": updated_state,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Answer processing error: {e}")


@app.post("/preview/harnessed/api/game/reset")
def harnessed_api_reset():
    global _harnessed_game_state
    try:
        g_mod = _get_workspace_module(HARNESSED_DIR, "game_engine")
        _harnessed_game_state = g_mod.get_initial_state()
        return {"message": "Game reset successfully", "game_state": _harnessed_game_state}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
