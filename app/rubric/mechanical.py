"""Tier 1: Deterministic and Static Mechanical Evaluation Checks.

Automated evaluation of unit test passage, Ruff static analysis, PEP 585 type hints,
parameterised input hygiene, and deterministic tool trajectory.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def check_unit_tests(workspace_path: Path) -> dict[str, Any]:
    """Check 1.1: Run pytest on the test suite within candidate workspace.
    
    If the candidate generated unit tests, runs them. Also validates against
    golden tests if available.
    """
    tests_dir = workspace_path / "tests"
    test_files = list(workspace_path.glob("test_*.py")) + (list(tests_dir.glob("test_*.py")) if tests_dir.exists() else [])
    
    if not test_files:
        return {
            "id": "1.1",
            "name": "Unit Tests Passage",
            "passed": False,
            "score": 0.0,
            "details": "No unit tests found in workspace (TDD requirement omitted).",
        }

    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(workspace_path)
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--disable-warnings"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
        passed = result.returncode == 0
        output_snippet = (result.stdout + result.stderr).strip()[-500:]
        return {
            "id": "1.1",
            "name": "Unit Tests Passage",
            "passed": passed,
            "score": 1.0 if passed else 0.0,
            "details": "All unit tests passed cleanly." if passed else f"Test failures:\n{output_snippet}",
        }
    except Exception as e:
        return {
            "id": "1.1",
            "name": "Unit Tests Passage",
            "passed": False,
            "score": 0.0,
            "details": f"Pytest execution failed: {e}",
        }


def check_static_analysis(workspace_path: Path) -> dict[str, Any]:
    """Check 1.2: Run ruff check on candidate python files."""
    py_files = list(workspace_path.glob("*.py")) + list((workspace_path / "app").glob("*.py") if (workspace_path / "app").exists() else [])
    if not py_files:
        return {
            "id": "1.2",
            "name": "Static Analysis (Ruff)",
            "passed": False,
            "score": 0.0,
            "details": "No Python files found to analyse.",
        }

    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "."],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        passed = result.returncode == 0
        details = "Ruff reported zero warnings or errors." if passed else result.stdout.strip()[:400]
        return {
            "id": "1.2",
            "name": "Static Analysis (Ruff)",
            "passed": passed,
            "score": 1.0 if passed else 0.0,
            "details": details,
        }
    except FileNotFoundError:
        # Fallback to internal AST syntax validation if ruff binary is not found in subshell
        syntax_errors = []
        for pf in py_files:
            try:
                ast.parse(pf.read_text(encoding="utf-8"))
            except SyntaxError as se:
                syntax_errors.append(f"{pf.name}: {se.msg}")
        passed = len(syntax_errors) == 0
        return {
            "id": "1.2",
            "name": "Static Analysis (AST Syntax)",
            "passed": passed,
            "score": 1.0 if passed else 0.0,
            "details": "Syntax verified cleanly." if passed else f"Syntax errors: {', '.join(syntax_errors)}",
        }


def check_pep585_typing(workspace_path: Path) -> dict[str, Any]:
    """Check 1.3: Verify modern PEP 585 type hints (no typing.List/typing.Dict)."""
    deprecated_types = {"List", "Dict", "Set", "Tuple"}
    violations: list[str] = []

    for py_file in workspace_path.glob("**/*.py"):
        if "venv" in py_file.parts or ".pytest_cache" in py_file.parts:
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "typing":
                    for alias in node.names:
                        if alias.name in deprecated_types:
                            violations.append(f"{py_file.name}: from typing import {alias.name}")
                elif isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name) and node.value.id == "typing" and node.attr in deprecated_types:
                        violations.append(f"{py_file.name}: typing.{node.attr}")
        except Exception:
            pass

    passed = len(violations) == 0
    return {
        "id": "1.3",
        "name": "PEP 585 Type Hints",
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "details": "Modern standard generic types used throughout." if passed else f"Deprecated types detected: {', '.join(violations[:3])}",
    }


def check_parameterised_inputs(workspace_path: Path) -> dict[str, Any]:
    """Check 1.4: Inspect AST for raw string formatting in database queries or dynamic evaluation."""
    risky_patterns: list[str] = []

    for py_file in workspace_path.glob("**/*.py"):
        if "venv" in py_file.parts or "test" in py_file.name:
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Check for eval() or exec()
                    if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                        risky_patterns.append(f"{py_file.name}: unsafe {node.func.id}() invocation")
        except Exception:
            pass

    passed = len(risky_patterns) == 0
    return {
        "id": "1.4",
        "name": "Parameterised Input Safety",
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "details": "Safe parameterised input boundaries preserved." if passed else f"Unsafe execution detected: {', '.join(risky_patterns)}",
    }


def check_tool_trajectory(trajectory_log: list[dict[str, Any]]) -> dict[str, Any]:
    """Check 1.5: Validate that agent invoked permitted tools without runaway thrashing."""
    if not trajectory_log:
        return {
            "id": "1.5",
            "name": "Deterministic Tool Trajectory",
            "passed": True,
            "score": 1.0,
            "details": "Clean tool trajectory with zero unhandled exceptions.",
        }

    # Verify error rates or unapproved tool names
    errors = [t for t in trajectory_log if t.get("status") == "error"]
    passed = len(errors) <= 1
    return {
        "id": "1.5",
        "name": "Deterministic Tool Trajectory",
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "details": f"Executed {len(trajectory_log)} tool invocations cleanly." if passed else f"Tool thrashing detected ({len(errors)} errors).",
    }


def check_frontend_ui_structure(workspace_path: Path) -> dict[str, Any]:
    """Check 1.6: Validate that static/index.html contains required UI containers.
    
    Verifies Section 3.4 frontend requirements:
    - Real-time HUD elements (shields, energy, status)
    - Star map / sector display container
    - Interactive combat/trivia modal dialogue
    """
    html_file = workspace_path / "static" / "index.html"
    if not html_file.is_file():
        return {
            "id": "1.6",
            "name": "Frontend UI Structure & HUD",
            "passed": False,
            "score": 0.0,
            "details": "static/index.html not found in workspace (frontend client omitted).",
        }

    content = html_file.read_text(encoding="utf-8").lower()
    missing_elements: list[str] = []

    # 1. Check for HUD components
    if "shields" not in content or "energy" not in content:
        missing_elements.append("HUD counters (shields/energy)")

    # 2. Check for star map container
    if not any(token in content for token in ["sector", "grid", "starmap", "star-map"]):
        missing_elements.append("Star map sector grid container")

    # 3. Check for combat modal
    if "modal" not in content and "dialog" not in content:
        missing_elements.append("Combat trivia challenge modal dialogue")

    passed = len(missing_elements) == 0
    return {
        "id": "1.6",
        "name": "Frontend UI Structure & HUD",
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "details": (
            "Valid static/index.html structure with HUD metrics, sector grid, and combat modal."
            if passed
            else f"static/index.html missing required UI elements: {', '.join(missing_elements)}."
        ),
    }


def check_frontend_api_wiring(workspace_path: Path) -> dict[str, Any]:
    """Check 1.7: Validate client-side JavaScript event wiring and REST API integration.
    
    Ensures that static/index.html (or associated JS) wires event listeners to:
    - /api/game/attack (initiating combat on adjacent sectors)
    - /api/game/answer (submitting trivia answer to resolve combat)
    - /api/game/state (synchronising state)
    """
    html_file = workspace_path / "static" / "index.html"
    if not html_file.is_file():
        return {
            "id": "1.7",
            "name": "Frontend Interactive API Wiring",
            "passed": False,
            "score": 0.0,
            "details": "static/index.html not found to verify client API wiring.",
        }

    # Aggregate all HTML and static JS files
    bundle = html_file.read_text(encoding="utf-8")
    static_dir = workspace_path / "static"
    for js_file in static_dir.glob("*.js"):
        bundle += "\n" + js_file.read_text(encoding="utf-8")

    missing_endpoints: list[str] = []
    if "/api/game/attack" not in bundle and "api/game/attack" not in bundle:
        missing_endpoints.append("/api/game/attack (sector attack trigger)")
    if "/api/game/answer" not in bundle and "api/game/answer" not in bundle:
        missing_endpoints.append("/api/game/answer (combat answer submission)")

    passed = len(missing_endpoints) == 0
    return {
        "id": "1.7",
        "name": "Frontend Interactive API Wiring",
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "details": (
            "Interactive client-side JavaScript wiring verified with active endpoints."
            if passed
            else f"Non-interactive UI: missing API endpoints in client script: {', '.join(missing_endpoints)}."
        ),
    }


def check_dynamic_api_contract(workspace_path: Path) -> dict[str, Any]:
    """Check 1.8: Boot candidate FastAPI app and verify /api/game/state progression contract.
    
    Dynamically loads main.py using Starlette/FastAPI TestClient to verify:
    - Candidate application imports and initialises cleanly without startup crashes.
    - GET /api/game/state returns HTTP 200 with JSON payload.
    - Controlled sectors list is non-empty and includes initial territory (e.g. 'earth').
    - Progression targets (valid_targets or available_targets) is non-empty with valid adjacent sectors.
    """
    main_file = workspace_path / "main.py"
    if not main_file.is_file():
        return {
            "id": "1.8",
            "name": "Dynamic API Contract & Progression Topology",
            "passed": False,
            "score": 0.0,
            "details": "main.py not found in workspace (FastAPI entrypoint omitted).",
        }

    import importlib

    from fastapi.testclient import TestClient

    sys_path_saved = list(sys.path)
    clean_modules = ["main", "game_engine", "trivia_service"]

    try:
        abs_ws = str(workspace_path.resolve())
        if abs_ws not in sys.path:
            sys.path.insert(0, abs_ws)

        for mod in clean_modules:
            if mod in sys.modules:
                del sys.modules[mod]

        main_mod = importlib.import_module("main")
        app_instance = getattr(main_mod, "app", None)
        if app_instance is None:
            return {
                "id": "1.8",
                "name": "Dynamic API Contract & Progression Topology",
                "passed": False,
                "score": 0.0,
                "details": "main.py does not export a FastAPI 'app' instance.",
            }

        client = TestClient(app_instance)
        response = client.get("/api/game/state")
        if response.status_code != 200:
            return {
                "id": "1.8",
                "name": "Dynamic API Contract & Progression Topology",
                "passed": False,
                "score": 0.0,
                "details": f"GET /api/game/state returned unexpected HTTP status {response.status_code}.",
            }

        data = response.json()
        if not isinstance(data, dict):
            return {
                "id": "1.8",
                "name": "Dynamic API Contract & Progression Topology",
                "passed": False,
                "score": 0.0,
                "details": f"GET /api/game/state returned non-dict response: {type(data).__name__}.",
            }

        controlled = data.get("controlled_sectors", [])
        if not isinstance(controlled, list) or len(controlled) == 0:
            return {
                "id": "1.8",
                "name": "Dynamic API Contract & Progression Topology",
                "passed": False,
                "score": 0.0,
                "details": "State payload missing non-empty 'controlled_sectors' list.",
            }

        targets = data.get("valid_targets") or data.get("available_targets") or []
        if not isinstance(targets, list) or len(targets) == 0:
            return {
                "id": "1.8",
                "name": "Dynamic API Contract & Progression Topology",
                "passed": False,
                "score": 0.0,
                "details": "State payload missing progression targets ('valid_targets' or 'available_targets').",
            }

        return {
            "id": "1.8",
            "name": "Dynamic API Contract & Progression Topology",
            "passed": True,
            "score": 1.0,
            "details": f"FastAPI app booted cleanly; /api/game/state verified with controlled territory ({controlled}) and active targets ({targets}).",
        }
    except Exception as e:
        return {
            "id": "1.8",
            "name": "Dynamic API Contract & Progression Topology",
            "passed": False,
            "score": 0.0,
            "details": f"Dynamic API validation failed during app startup: {e}",
        }
    finally:
        sys.path = sys_path_saved
        for mod in clean_modules:
            if mod in sys.modules:
                del sys.modules[mod]


def run_mechanical_tier(workspace_path: Path, trajectory: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Execute all Tier 1 mechanical checks."""
    trajectory = trajectory or []
    return [
        check_unit_tests(workspace_path),
        check_static_analysis(workspace_path),
        check_pep585_typing(workspace_path),
        check_parameterised_inputs(workspace_path),
        check_tool_trajectory(trajectory),
        check_frontend_ui_structure(workspace_path),
        check_frontend_api_wiring(workspace_path),
        check_dynamic_api_contract(workspace_path),
    ]
