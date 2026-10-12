"""Reusable Google ADK FunctionTools for Autonomous Loop Engineering Harnesses.

Provides workspace-scoped tools that equip an ADK `Agent` (`LlmAgent`) to:
1. Dynamically load specialised `SKILL.md` engineering skills on demand (`activate_skill`).
2. Author, update, and inspect files safely inside an isolated workspace (`write_workspace_file`, `read_workspace_file`).
3. Execute automated unit test suites (`run_pytest`) and static analysis linters (`run_ruff_check`).
4. Record deterministic tool trajectory telemetry in `tool_context.state["tool_trajectory"]`.

Consumers building their own ADK coding harnesses can copy or import `HARNESS_TOOLS`
directly and bind the target directory via `session.state["workspace_path"]`.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from google.adk.tools import ToolContext

from app.config import load_harness_skills

# Display metadata for Workbench UI skill badges and event cards
SKILL_METADATA: dict[str, dict[str, str]] = {
    "test-driven-development": {
        "name": "Test-Driven Development (TDD)",
        "rationale": "Enforces red-green-refactor loop covering star map adjacency and combat mechanics.",
    },
    "api-and-interface-design": {
        "name": "API & Interface Design",
        "rationale": "Guarantees parameter validation and rejection of invalid sector attacks with actionable error details.",
    },
    "gemini-api-dev": {
        "name": "Gemini API Development",
        "rationale": "Restricts trivia questions strictly to real canonical films (e.g. Blade Runner, Alien, The Matrix, Dune).",
    },
}


def _record_trajectory(tool_context: ToolContext, tool_name: str, status: str, detail: str = "") -> None:
    """Append a structured tool execution entry to the session trajectory log."""
    trajectory = list(tool_context.state.get("tool_trajectory", []))
    trajectory.append(
        {
            "tool": tool_name,
            "status": status,
            "detail": detail,
        }
    )
    tool_context.state["tool_trajectory"] = trajectory


def _resolve_safe_workspace_path(tool_context: ToolContext, relative_path: str) -> tuple[Path | None, str]:
    """Resolve `relative_path` strictly inside the session's `workspace_path`."""
    raw_ws = tool_context.state.get("workspace_path", "")
    if not raw_ws:
        return None, "Session state missing 'workspace_path'."

    ws_root = Path(raw_ws).resolve()
    cleaned_rel = relative_path.strip().lstrip("/\\")
    if not cleaned_rel:
        return None, "Relative file path must not be empty."

    # Enforce strict sandbox containment: reject any relative path or symlink that
    # resolves outside ws_root (e.g. '../../app/main.py') before touching the filesystem.
    candidate = (ws_root / cleaned_rel).resolve()
    try:
        candidate.relative_to(ws_root)
    except ValueError:
        return None, f"Path traversal outside workspace rejected: '{relative_path}'."

    return candidate, cleaned_rel


def activate_skill(skill_name: str, tool_context: ToolContext) -> dict[str, Any]:
    """Load a specialised engineering skill (SKILL.md) into the agent context on demand.

    Args:
        skill_name: Identifier of the skill to load (e.g. 'test-driven-development',
            'api-and-interface-design', or 'gemini-api-dev').

    Returns:
        dict containing 'status', 'skill', and the loaded 'instructions' markdown.
    """
    skills = load_harness_skills()
    normalised = skill_name.strip().lower()
    if normalised not in skills:
        _record_trajectory(
            tool_context,
            "activate_skill",
            "error",
            f"Unknown skill '{skill_name}'. Available: {list(skills.keys())}",
        )
        return {
            "status": "error",
            "skill": normalised,
            "message": f"Skill '{skill_name}' not found. Available skills: {sorted(skills.keys())}",
        }

    activated = list(tool_context.state.get("activated_skills", []))
    if normalised not in activated:
        activated.append(normalised)
        tool_context.state["activated_skills"] = activated

    _record_trajectory(tool_context, "activate_skill", "ok", normalised)
    meta = SKILL_METADATA.get(
        normalised,
        {"name": normalised, "rationale": "Loaded specialised engineering skill instructions."},
    )
    return {
        "status": "ok",
        "skill": normalised,
        "name": meta["name"],
        "rationale": meta["rationale"],
        "instructions": skills[normalised],
    }


def write_workspace_file(
    relative_path: str,
    content: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Create or overwrite a source or test file inside the candidate workspace.

    Args:
        relative_path: File path relative to the workspace root (e.g. 'tests/test_game.py',
            'game_engine.py', 'trivia_service.py', 'main.py', or 'static/index.html').
        content: Complete UTF-8 text content to write to the file.

    Returns:
        dict with 'status', 'file', and 'bytes_written'.
    """
    target_path, rel_or_err = _resolve_safe_workspace_path(tool_context, relative_path)
    if target_path is None:
        _record_trajectory(tool_context, "write_workspace_file", "error", rel_or_err)
        return {"status": "error", "message": rel_or_err}

    if target_path.is_dir():
        _record_trajectory(
            tool_context,
            "write_workspace_file",
            "error",
            f"Target '{rel_or_err}' is a directory.",
        )
        return {
            "status": "error",
            "message": f"Target path '{rel_or_err}' is a directory, not a file.",
        }

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")

    modified = list(tool_context.state.get("files_modified_in_iteration", []))
    if rel_or_err not in modified:
        modified.append(rel_or_err)
        tool_context.state["files_modified_in_iteration"] = modified

    _record_trajectory(tool_context, "write_workspace_file", "ok", rel_or_err)
    return {
        "status": "ok",
        "file": rel_or_err,
        "bytes_written": len(content.encode("utf-8")),
    }


def read_workspace_file(relative_path: str, tool_context: ToolContext) -> dict[str, Any]:
    """Read the contents of an existing file inside the candidate workspace.

    Args:
        relative_path: File path relative to the workspace root (e.g. 'main.py').

    Returns:
        dict with 'status', 'file', and 'content'.
    """
    target_path, rel_or_err = _resolve_safe_workspace_path(tool_context, relative_path)
    if target_path is None:
        _record_trajectory(tool_context, "read_workspace_file", "error", rel_or_err)
        return {"status": "error", "message": rel_or_err}

    if not target_path.is_file():
        _record_trajectory(tool_context, "read_workspace_file", "error", f"Not found: {rel_or_err}")
        return {"status": "error", "file": rel_or_err, "message": f"File '{rel_or_err}' does not exist."}

    text = target_path.read_text(encoding="utf-8")
    _record_trajectory(tool_context, "read_workspace_file", "ok", rel_or_err)
    return {
        "status": "ok",
        "file": rel_or_err,
        "content": text,
    }


def run_pytest(tool_context: ToolContext) -> dict[str, Any]:
    """Execute the pytest unit test suite inside the candidate workspace.

    Returns:
        dict with 'status' ('passed', 'failed', or 'skipped'), 'returncode', and test 'output'.
    """
    raw_ws = tool_context.state.get("workspace_path", "")
    if not raw_ws or not Path(raw_ws).is_dir():
        _record_trajectory(tool_context, "run_pytest", "error", "Invalid workspace_path")
        return {"status": "error", "message": "Workspace directory does not exist."}

    ws_path = Path(raw_ws).resolve()
    tests_dir = ws_path / "tests"
    # Pre-check for test_*.py files: pytest exits with returncode 5 ("no tests collected")
    # when invoked on an empty workspace, which would otherwise be misreported as a test failure.
    test_files = list(ws_path.glob("test_*.py")) + (
        list(tests_dir.glob("test_*.py")) if tests_dir.exists() else []
    )
    if not test_files:
        _record_trajectory(tool_context, "run_pytest", "skipped", "No test files present yet")
        return {
            "status": "skipped",
            "returncode": 0,
            "output": "Skipped: no unit test files authored in workspace yet.",
        }

    # Inject ws_path into PYTHONPATH so tests inside tests/test_game.py can import
    # top-level candidate modules (e.g. `from game_engine import ...`).
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ws_path)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--disable-warnings"],
            cwd=ws_path,
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
        output = (result.stdout + result.stderr).strip()[-1000:]
        passed = result.returncode == 0
        status = "passed" if passed else "failed"
        _record_trajectory(tool_context, "run_pytest", "ok", status)
        return {
            "status": status,
            "returncode": result.returncode,
            "output": output or ("All unit tests passed." if passed else "Unit test failure."),
        }
    except Exception as exc:
        _record_trajectory(tool_context, "run_pytest", "error", str(exc))
        return {"status": "error", "message": f"Pytest execution failed: {exc}"}


def run_ruff_check(tool_context: ToolContext) -> dict[str, Any]:
    """Execute Ruff static analysis and auto-fixing (`ruff check --fix .`) on the workspace.

    Returns:
        dict with 'status' ('passed', 'failed', or 'skipped'), 'returncode', and linter 'output'.
    """
    raw_ws = tool_context.state.get("workspace_path", "")
    if not raw_ws or not Path(raw_ws).is_dir():
        _record_trajectory(tool_context, "run_ruff_check", "error", "Invalid workspace_path")
        return {"status": "error", "message": "Workspace directory does not exist."}

    ws_path = Path(raw_ws).resolve()
    # Pre-check for *.py files: running `ruff check` on a workspace containing only README.md
    # emits `All checks passed!\nwarning: No Python files found under the given path(s)`,
    # which would surface a misleading warning card in the Workbench UI feed.
    py_files = [
        p
        for p in ws_path.rglob("*.py")
        if ".pytest_cache" not in p.parts and ".ruff_cache" not in p.parts
    ]
    if not py_files:
        _record_trajectory(tool_context, "run_ruff_check", "skipped", "No Python files present yet")
        return {
            "status": "skipped",
            "returncode": 0,
            "output": "Skipped: no Python files authored in workspace yet.",
        }

    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--fix", "."],
            cwd=ws_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = (result.stdout + result.stderr).strip()[-1000:]
        passed = result.returncode == 0
        status = "passed" if passed else "failed"
        if passed and ("All checks passed" in output or "0 remaining" in output or not output):
            clean_output = "All checks passed cleanly."
        else:
            clean_output = output
        _record_trajectory(tool_context, "run_ruff_check", "ok", status)
        return {
            "status": status,
            "returncode": result.returncode,
            "output": clean_output,
        }
    except Exception as exc:
        _record_trajectory(tool_context, "run_ruff_check", "error", str(exc))
        return {"status": "error", "message": f"Ruff check failed: {exc}"}


HARNESS_TOOLS = (
    activate_skill,
    write_workspace_file,
    read_workspace_file,
    run_pytest,
    run_ruff_check,
)

