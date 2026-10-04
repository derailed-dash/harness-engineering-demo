"""Tests for workbench index page and spec modal delivery.

This module validates that the Harness Engineering Workbench serves the shared goal
specification directly embedded into the initial HTML document with zero network latency,
that the obsolete loading spinner element is removed, and that the GET /api/spec
endpoint remains functional for API consumers.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_index_spec_content_embedded() -> None:
    """Verify GET / embeds spec content directly and eliminates loading spinner."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # Loading spinner must be removed
    assert "spec-modal-loading" not in html

    # Spec elements must be present
    assert 'id="spec-content-data"' in html
    assert 'id="spec-rendered-view"' in html
    assert 'id="spec-raw-view"' in html
    assert 'id="spec-raw-code"' in html

    # Per-panel timing and preview elements must be present
    assert 'id="unharnessed-time"' in html
    assert 'id="harnessed-time"' in html
    assert 'id="harnessed-preview-ready"' in html
    assert 'id="unharnessed-preview-ready"' in html

    # Check that actual spec content text is embedded without HTML entity escaping
    assert "Cosmic Trivia & Strategy Conquest" in html
    assert '{"target_sector": "lv426"}' in html
    assert "&#34;target_sector&#34;" not in html


def test_api_spec_endpoint_preserved() -> None:
    """Verify GET /api/spec continues to serve the specification for API consumers."""
    client = TestClient(app)
    response = client.get("/api/spec")
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "specs/cosmic_conquest_spec.md"
    assert "Cosmic Trivia & Strategy Conquest" in data["content"]


def test_index_harness_context_embedded() -> None:
    """Verify GET / embeds harness context content and clickable UI triggers."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # Harness context container must be present
    assert 'id="harness-context-data"' in html

    # Clickable buttons and links must be present
    assert "openHarnessContextModal()" in html
    assert "specs/harness_context.md" in html

    # Verify key harness guardrail phrases are embedded
    assert "Engineering Context & Harness Guardrails" in html
    assert "Strict PEP 585" in html


def test_api_harness_context_endpoint() -> None:
    """Verify GET /api/harness-context serves harness guardrails for API consumers."""
    client = TestClient(app)
    response = client.get("/api/harness-context")
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "specs/harness_context.md"
    assert "Engineering Context & Harness Guardrails" in data["title"]
    assert "Strict PEP 585" in data["content"]


def test_preview_endpoints_cleared_after_reset() -> None:
    """Verify that calling /api/reset resets preview frames to awaiting placeholders."""
    from app.replay.player import restore_replay_workspaces

    client = TestClient(app)

    # First ensure candidate workspaces are populated
    restore_replay_workspaces()
    res_h = client.get("/preview/harnessed")
    assert res_h.status_code == 200
    assert "Cosmic" in res_h.text

    res_u = client.get("/preview/unharnessed")
    assert res_u.status_code == 200
    assert "Cosmic" in res_u.text

    # Trigger reset endpoint
    reset_res = client.post("/api/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "ok"

    # Previews must now return pristine placeholder HTML
    cleared_h = client.get("/preview/harnessed")
    assert cleared_h.status_code == 200
    assert "Harnessed Workspace Preview" in cleared_h.text
    assert "Status: Awaiting harness loop run." in cleared_h.text

    cleared_u = client.get("/preview/unharnessed")
    assert cleared_u.status_code == 200
    assert "Unharnessed Workspace Preview" in cleared_u.text
    assert "Status: Awaiting generation run." in cleared_u.text

    # Re-populate workspaces cleanly so subsequent test runs remain valid
    restore_replay_workspaces()

