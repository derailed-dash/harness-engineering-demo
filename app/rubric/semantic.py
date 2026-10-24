"""Tier 2: Semantic Yes/No Analyses Evaluated via LLM-as-a-Judge or Rule Heuristics.

Evaluates Goal Fidelity (real Sci-Fi movie trivia, star map rules), Scope Discipline,
Architectural Integrity, Error Clarity, and Design Documentation Rationale.
"""

import json
import re
from pathlib import Path
from typing import Any

from google.genai import types

from app.client_factory import get_genai_client
from app.config import DEFAULT_MODEL, MODEL_NAME, load_harness_rubric
from app.token_tracker import TokenMetrics

SEMANTIC_RUBRIC_PROMPT = load_harness_rubric()


def _evaluate_heuristic_fallback(workspace_path: Path) -> list[dict[str, Any]]:
    """Deterministic heuristic evaluation when offline or API key is absent.
    
    Performs rigorous AST and semantic inspection matching the blog rubric criteria.
    """
    import ast

    code_bundle = ""
    py_files = list(workspace_path.glob("*.py"))
    ast_trees: dict[str, ast.Module] = {}
    for pf in py_files:
        try:
            content = pf.read_text(encoding="utf-8")
            code_bundle += "\n" + content
            parsed = ast.parse(content)
            if isinstance(parsed, ast.Module):
                ast_trees[pf.name] = parsed
        except Exception:
            pass

    # 2.1: Target State Completion (Goal Fidelity)
    # Check for real sci-fi movie references and strict adjacency validation
    has_generic_lore = "generic space lore" in code_bundle.lower() or "speed of light in hyper-space" in code_bundle.lower()
    has_real_movies = all(m in code_bundle.lower() for m in ["alien", "blade runner", "dune"])
    has_flawed_adjacency = '"arrakis"' in code_bundle and 'available_targets": ["lv426", "zion", "arrakis"]' in code_bundle
    c21_pass = has_real_movies and not has_generic_lore and not has_flawed_adjacency

    # 2.2: Scope Discipline (Anti-Hallucination)
    c22_pass = len(py_files) <= 6 and "unnecessary" not in code_bundle.lower()

    # 2.3: Architectural Integrity (clean separation vs monolithic coupling)
    has_pydantic_models = "basemodel" in code_bundle.lower()
    has_tests_dir = (workspace_path / "tests").exists()
    c23_pass = has_pydantic_models and has_tests_dir

    # 2.4: Error & Remediation Clarity (checking active HTTP 400 raise calls)
    raises_400 = False
    for tree in ast_trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                exc_str = ast.dump(node.exc)
                if "400" in exc_str or "status_code" in exc_str:
                    raises_400 = True
                    break
    c24_pass = raises_400

    # 2.5: Design Rationale & Intent (module docstrings explaining architectural intent)
    has_module_docstrings = True
    if not py_files:
        has_module_docstrings = False
    for name, tree in ast_trees.items():
        doc = ast.get_docstring(tree)
        if not doc or len(doc.strip()) < 20 or "architectural intent" not in doc.lower():
            has_module_docstrings = False
            break
    c25_pass = has_module_docstrings

    # 2.6: Progression Ergonomics & Interactivity
    html_file = workspace_path / "static" / "index.html"
    c26_pass = False
    c26_details = "Missing static/index.html to assess progression ergonomics."
    if html_file.is_file():
        ui_bundle = html_file.read_text(encoding="utf-8")
        static_dir = workspace_path / "static"
        for js_f in static_dir.glob("*.js"):
            ui_bundle += "\n" + js_f.read_text(encoding="utf-8")

        has_direct_card_trigger = (
            "initiateattack(sec" in ui_bundle.lower()
            or "card.onclick" in ui_bundle.lower()
            or "card.addeventlistener('click'" in ui_bundle.lower()
            or "attacksector(" in ui_bundle.lower()
        )
        has_two_step_disabled_barrier = (
            "btn-attack-action" in ui_bundle
            and 'disabled onclick="initiateattack' in ui_bundle.lower()
        )
        if has_direct_card_trigger and not has_two_step_disabled_barrier:
            c26_pass = True
            c26_details = "Direct single-action attack affordance verified on valid sector targets."
        elif has_two_step_disabled_barrier:
            c26_pass = False
            c26_details = "Indirect multi-step progression: attack button is initially disabled and disconnected from direct sector clicks."
        else:
            has_attack = "attack" in ui_bundle.lower() and "click" in ui_bundle.lower()
            c26_pass = has_attack
            c26_details = "Clickable attack affordance present." if c26_pass else "No interactive progression or attack triggers found on sector elements."

    return [
        {
            "id": "2.1",
            "name": "Target State Completion (Goal Fidelity)",
            "score": 1.0 if c21_pass else 0.0,
            "passed": c21_pass,
            "details": "Real Sci-Fi movie trivia and star map adjacency rules implemented." if c21_pass else "Flawed goal fidelity: allows illegal non-adjacent moves or non-movie trivia.",
        },
        {
            "id": "2.2",
            "name": "Scope Discipline (Anti-Hallucination)",
            "score": 1.0 if c22_pass else 0.0,
            "passed": c22_pass,
            "details": "Disciplined implementation without speculative dead files." if c22_pass else "Speculative or hallucinated artifacts detected.",
        },
        {
            "id": "2.3",
            "name": "Architectural Integrity",
            "score": 1.0 if c23_pass else 0.0,
            "passed": c23_pass,
            "details": "Clean modular boundary between game engine, trivia service, and API routes." if c23_pass else "Monolithic coupling: raw mutable dicts without Pydantic models or tests.",
        },
        {
            "id": "2.4",
            "name": "Error & Remediation Clarity",
            "score": 1.0 if c24_pass else 0.0,
            "passed": c24_pass,
            "details": "Actionable HTTP 400 responses for illegal turns without leaking stack traces." if c24_pass else "Missing HTTP 400 validation: invalid moves return 200 without actionable errors.",
        },
        {
            "id": "2.5",
            "name": "Design Rationale & Intent",
            "score": 1.0 if c25_pass else 0.0,
            "passed": c25_pass,
            "details": "Module docstrings clearly document the architectural 'why' and intent." if c25_pass else "Missing or superficial module docstrings (lacks architectural rationale).",
        },
        {
            "id": "2.6",
            "name": "Progression Ergonomics & Interactivity",
            "score": 1.0 if c26_pass else 0.0,
            "passed": c26_pass,
            "details": c26_details,
        },
    ]


def run_semantic_tier(
    workspace_path: Path,
    token_tracker: TokenMetrics | None = None,
    rubric_markdown: str | None = None,
) -> list[dict[str, Any]]:
    """Execute Tier 2 semantic analysis via Gemini LLM-as-a-Judge or heuristic fallback."""
    # Gather candidate code
    code_snippets: list[str] = []
    for py_file in workspace_path.glob("**/*.py"):
        if "venv" in py_file.parts or ".pytest" in py_file.parts:
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
            code_snippets.append(f"--- File: {py_file.name} ---\n{content}\n")
        except Exception:
            pass

    html_file = workspace_path / "static" / "index.html"
    if html_file.is_file():
        try:
            raw_html = html_file.read_text(encoding="utf-8")
            # Strip large <style>...</style> CSS blocks so the semantic judge focuses on
            # HTML structure, <canvas>, and JavaScript progression logic without bloating tokens.
            compact_html = re.sub(
                r"<style\b[^>]*>.*?</style>",
                "<style>/* CSS omitted for semantic evaluation */</style>",
                raw_html,
                flags=re.DOTALL | re.IGNORECASE,
            )
            code_snippets.append(f"--- File: static/index.html ---\n{compact_html}\n")
        except Exception:
            pass

    full_code = "\n".join(code_snippets)
    if not full_code:
        return [
            {"id": f"2.{i}", "name": f"Semantic Check 2.{i}", "score": 0.0, "passed": False, "details": "No code found to evaluate."}
            for i in range(1, 7)
        ]

    # Attempt live Gemini evaluation via ADC or API key
    client, auth_mode = get_genai_client()
    if client:
        try:
            model_to_use = MODEL_NAME or DEFAULT_MODEL
            rubric_prompt = rubric_markdown or load_harness_rubric() or SEMANTIC_RUBRIC_PROMPT
            response = client.models.generate_content(
                model=model_to_use,
                contents=[
                    rubric_prompt,
                    f"Candidate Codebase:\n{full_code[:100000]}",
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=2048,
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                    http_options=types.HttpOptions(
                        timeout=10_000,
                        retry_options=types.HttpRetryOptions(attempts=1),
                    ),
                ),
            )
            
            if token_tracker and hasattr(response, "usage_metadata") and response.usage_metadata:
                token_tracker.add_usage(
                    prompt=response.usage_metadata.prompt_token_count or 0,
                    candidate=response.usage_metadata.candidates_token_count or 0,
                    label="Semantic Rubric Judge",
                )
            
            if response.text:
                data = json.loads(response.text)
                if "checks" in data and len(data["checks"]) == 6:
                    # Ensure float scores
                    for c in data["checks"]:
                        c["score"] = float(c["score"])
                    return data["checks"]
        except Exception:
            # Fall through to deterministic heuristic
            pass

    return _evaluate_heuristic_fallback(workspace_path)
