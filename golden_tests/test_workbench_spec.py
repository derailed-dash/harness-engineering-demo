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

    # Loading spinner and confusing external ARCHITECTURE.md link must be removed
    assert "spec-modal-loading" not in html
    assert "Read ARCHITECTURE.md" not in html

    # Spec elements must be present
    assert 'id="spec-content-data"' in html
    assert 'id="spec-rendered-view"' in html
    assert 'id="spec-raw-view"' in html
    assert 'id="spec-raw-code"' in html

    # Per-panel timing and preview elements must be present
    assert 'id="metric-status"' in html
    assert 'id="metric-time"' not in html
    assert 'id="metric-total-tokens"' not in html
    assert 'id="metric-total-cost"' not in html
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
    assert "harness/harness_context.md" in html

    # Verify key harness guardrail phrases are embedded
    assert "Engineering Context & Harness Guardrails" in html
    assert "Strict PEP 585" in html


def test_api_harness_context_endpoint() -> None:
    """Verify GET /api/harness-context serves harness guardrails for API consumers."""
    client = TestClient(app)
    response = client.get("/api/harness-context")
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "harness/harness_context.md"
    assert "Engineering Context & Harness Guardrails" in data["title"]
    assert "Strict PEP 585" in data["content"]


def test_api_rubric_endpoint_and_embedding() -> None:
    """Verify GET /api/rubric serves harness/RUBRIC.md and is embedded in the Workbench UI."""
    client = TestClient(app)
    response = client.get("/api/rubric")
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "harness/RUBRIC.md"
    assert "2.1 Target State Completion" in data["content"]
    assert "2.6 Progression Ergonomics" in data["content"]

    res_html = client.get("/")
    assert res_html.status_code == 200
    html = res_html.text
    assert 'id="rubric-content-data"' in html
    assert "openRubricModal()" in html
    assert "harness/RUBRIC.md" in html



def test_api_skills_endpoints_and_embedding() -> None:
    """Verify GET /api/skills and /api/skills/{skill_name} return specialised skills and are embedded in HTML."""
    client = TestClient(app)

    # 1. Test /api/skills listing
    res_list = client.get("/api/skills")
    assert res_list.status_code == 200
    skills_data = res_list.json()
    assert skills_data["count"] == 3
    assert "test-driven-development" in skills_data["skills"]
    assert "api-and-interface-design" in skills_data["skills"]
    assert "gemini-api-dev" in skills_data["skills"]

    # 2. Test individual skill endpoint
    res_tdd = client.get("/api/skills/test-driven-development")
    assert res_tdd.status_code == 200
    tdd_data = res_tdd.json()
    assert tdd_data["skill"] == "test-driven-development"
    assert "harness/skills/test-driven-development/SKILL.md" in tdd_data["filename"]
    assert "RED" in tdd_data["content"]
    assert "GREEN" in tdd_data["content"]

    # 3. Test missing skill returns 404
    res_404 = client.get("/api/skills/unknown-skill")
    assert res_404.status_code == 404

    # 4. Test skills are embedded in index HTML and have click triggers
    res_html = client.get("/")
    assert res_html.status_code == 200
    html = res_html.text
    assert 'id="skill-content-test-driven-development"' in html
    assert 'id="skill-content-api-and-interface-design"' in html
    assert 'id="skill-content-gemini-api-dev"' in html
    assert "openSkillModal('test-driven-development')" in html
    assert "openSkillModal('api-and-interface-design')" in html
    assert "openSkillModal('gemini-api-dev')" in html


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


def test_living_memory_persistence_reset_and_ui() -> None:
    """Verify that living memory is persisted to disk, cleared on reset, and exposed via API and UI."""
    from app.config import LIVING_MEMORY_PATH
    from app.replay.player import restore_replay_workspaces

    client = TestClient(app)

    # 1. Populate candidate workspaces / replay data which initialises living memory
    restore_replay_workspaces()
    assert LIVING_MEMORY_PATH.exists()
    content = LIVING_MEMORY_PATH.read_text(encoding="utf-8")
    assert "Living Memory & Diagnostic Ledger" in content
    assert "Iteration 1" in content
    assert "Iteration 2" in content
    assert "State Mutation Guard" in content

    # 2. Test GET /api/living-memory
    res = client.get("/api/living-memory")
    assert res.status_code == 200
    data = res.json()
    assert data["filename"] == "harness/output/LIVING_MEMORY.md"
    assert "Autonomous Living Memory" in data["title"]
    assert "Iteration 1" in data["content"]
    assert "Iteration 2" in data["content"]

    # 3. Test index HTML embedding & modal triggers
    res_html = client.get("/")
    assert res_html.status_code == 200
    html = res_html.text
    assert 'id="living-memory-data"' in html
    assert "openLivingMemoryModal()" in html
    assert "harness/output/LIVING_MEMORY.md" in html

    # 4. Test /api/reset clears living memory ledger
    reset_res = client.post("/api/reset")
    assert reset_res.status_code == 200
    assert not LIVING_MEMORY_PATH.exists()

    # When missing, /api/living-memory returns placeholder
    res_empty = client.get("/api/living-memory")
    assert res_empty.status_code == 200
    assert "No active run" in res_empty.json()["content"]

    # Re-populate workspaces for next tests
    restore_replay_workspaces()


def test_workbench_kill_run_toggle_ui_and_assets() -> None:
    """Verify Run Comparison <-> Kill Run toggle button markup, JS controller, and CSS styles."""
    from app.config import BASE_DIR

    client = TestClient(app)
    res_html = client.get("/")
    assert res_html.status_code == 200
    html = res_html.text

    # Header buttons must have explicit IDs for toggling and disabling
    assert 'id="btn-compare"' in html
    assert 'id="btn-replay"' in html
    assert 'id="btn-reset"' in html

    # Workbench JS must implement Kill Run toggle, SSE abort, and /api/cancel call
    js_path = BASE_DIR / "app" / "static" / "js" / "workbench.js"
    js_content = js_path.read_text(encoding="utf-8")
    assert "setComparisonRunningState" in js_content
    assert "killComparisonRun" in js_content
    assert "Kill Run" in js_content
    assert "Comparison Run Killed by User" in js_content
    assert "activeEventSource.close()" in js_content
    assert "activeEventSource = null" in js_content
    assert "stopTimer()" in js_content
    assert "fetch('/api/cancel'" in js_content

    # Workbench CSS must define danger/kill visual classes and disabled states
    css_path = BASE_DIR / "app" / "static" / "css" / "workbench.css"
    css_content = css_path.read_text(encoding="utf-8")
    assert ".btn-kill" in css_content
    assert ".is-running" in css_content
    assert "button:disabled" in css_content


def test_api_cancel_endpoint_and_orchestrator_cancellation(monkeypatch) -> None:
    """Verify POST /api/cancel and SSE disconnect cleanly cancel running orchestrator tasks."""
    import asyncio
    from pathlib import Path
    from typing import Any, AsyncGenerator

    from app.main import orchestrator
    from app.replay.player import restore_replay_workspaces

    client = TestClient(app)

    # 1. Calling /api/cancel when idle returns cancelled status with was_running=False
    idle_res = client.post("/api/cancel")
    assert idle_res.status_code == 200
    idle_data = idle_res.json()
    assert idle_data["status"] == "cancelled"
    assert idle_data["was_running"] is False

    # 2. Simulate long-running pipelines to verify task cancellation on /api/cancel and SSE disconnect
    async def slow_unharnessed(_workspace: Path, _tokens: Any) -> AsyncGenerator[dict[str, Any], None]:
        yield {"stage": "starting", "message": "Unharnessed started"}
        await asyncio.sleep(60)

    async def slow_harnessed(_workspace: Path, _tokens: Any) -> AsyncGenerator[dict[str, Any], None]:
        yield {"stage": "starting", "message": "Harnessed started"}
        await asyncio.sleep(60)

    monkeypatch.setattr("app.orchestrator.run_unharnessed_pipeline", slow_unharnessed)
    monkeypatch.setattr("app.orchestrator.run_harnessed_pipeline", slow_harnessed)

    async def verify_cancel_and_disconnect() -> None:
        # Case A: Explicit cancel via POST /api/cancel while stream_comparison is active
        gen = orchestrator.stream_comparison()
        first_evt = await anext(gen)
        assert first_evt["type"] == "init"
        second_evt = await anext(gen)
        assert second_evt["type"] in {"unharnessed_start", "harnessed_start"}
        assert orchestrator.is_running is True
        task_u = orchestrator.unharnessed_task
        task_h = orchestrator.harnessed_task
        assert task_u is not None and not task_u.done()
        assert task_h is not None and not task_h.done()

        cancel_res = client.post("/api/cancel")
        assert cancel_res.status_code == 200
        cancel_payload = cancel_res.json()
        assert cancel_payload["status"] == "cancelled"
        assert cancel_payload["was_running"] is True
        assert "unharnessed_task" in cancel_payload["cancelled_tasks"]
        assert "harnessed_task" in cancel_payload["cancelled_tasks"]

        # Drain remaining buffered items; generator should exit without comparison_summary
        remaining = [evt async for evt in gen]
        assert all(evt.get("type") != "comparison_summary" for evt in remaining)
        await asyncio.sleep(0)
        assert task_u.cancelled() or task_u.done()
        assert task_h.cancelled() or task_h.done()
        assert orchestrator.is_running is False

        # Case B: Early SSE disconnect (aclose) cancels both worker tasks in finally block
        gen2 = orchestrator.stream_comparison()
        await anext(gen2)
        await anext(gen2)
        task_u2 = orchestrator.unharnessed_task
        task_h2 = orchestrator.harnessed_task
        assert task_u2 is not None and not task_u2.done()
        assert task_h2 is not None and not task_h2.done()

        await gen2.aclose()
        await asyncio.sleep(0)
        assert task_u2.cancelled() or task_u2.done()
        assert task_h2.cancelled() or task_h2.done()
        assert orchestrator.is_running is False

    asyncio.run(verify_cancel_and_disconnect())
    restore_replay_workspaces()
