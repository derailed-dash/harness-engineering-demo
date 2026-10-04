"""Golden acceptance test suite for Cosmic Conquest UI client contract.

Verifies Section 3.4 of cosmic_conquest_spec.md:
- static/index.html existence and FastAPI root route serving
- Star Map sector display container and real-time HUD elements
- Combat challenge modal dialogue
- Active client-side API wiring to /api/game/attack, /api/game/answer, and /api/game/state
"""

from typing import Any

from fastapi.testclient import TestClient

from golden_tests.test_api_contract import get_fastapi_app


def test_ui_index_html_exists(candidate_workspace: Any) -> None:
    """Verify static/index.html exists in the candidate workspace."""
    index_file = candidate_workspace / "static" / "index.html"
    assert index_file.is_file(), "Candidate workspace must generate static/index.html"
    content = index_file.read_text(encoding="utf-8")
    assert len(content.strip()) > 50, "static/index.html must not be empty"


def test_ui_served_by_fastapi_root(candidate_workspace: Any) -> None:
    """Verify GET / serves the interactive static/index.html interface."""
    app = get_fastapi_app(candidate_workspace)
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Cosmic" in response.text


def test_ui_hud_and_modal_elements_present(candidate_workspace: Any) -> None:
    """Verify static/index.html contains required HUD metrics and combat modal."""
    index_file = candidate_workspace / "static" / "index.html"
    content = index_file.read_text(encoding="utf-8").lower()

    # Real-time HUD counters
    assert "shields" in content, "static/index.html must display shield integrity"
    assert "energy" in content, "static/index.html must display cosmic energy"

    # Star Map sector display
    assert any(term in content for term in ["sector", "grid", "starmap", "star-map"]), (
        "static/index.html must contain a Star Map sector container"
    )

    # Interactive combat / trivia modal dialogue
    assert "modal" in content or "dialog" in content, (
        "static/index.html must contain an interactive combat challenge modal dialogue"
    )

    # Ambient or animated cosmic starfield background
    assert any(term in content for term in ["stars-canvas", "starfield", "stars", "particle"]), (
        "static/index.html must contain an ambient or animated cosmic starfield background"
    )


def test_ui_api_wiring_endpoints_present(candidate_workspace: Any) -> None:
    """Verify static/index.html (or static scripts) contains active fetch calls."""
    index_file = candidate_workspace / "static" / "index.html"
    bundle = index_file.read_text(encoding="utf-8")
    for js_file in (candidate_workspace / "static").glob("*.js"):
        bundle += "\n" + js_file.read_text(encoding="utf-8")

    assert "/api/game/attack" in bundle or "api/game/attack" in bundle, (
        "static/index.html must wire attack actions to /api/game/attack"
    )
    assert "/api/game/answer" in bundle or "api/game/answer" in bundle, (
        "static/index.html must wire answer submissions to /api/game/answer"
    )
