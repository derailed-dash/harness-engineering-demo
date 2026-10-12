"""Golden tests verifying Google ADK (google-adk) architecture for both tracks.

Validates that:
1. Track 1 (Unharnessed Single Pass) uses a bare ADK Agent with zero persona,
   zero extra context, and zero tools.
2. Track 2 (Harnessed Loop) uses a composite ADK LoopAgent combining an LlmAgent
   builder (with FunctionTools and dynamic state-driven instructions from
   harness/harness_context.md) and a custom BaseAgent rubric evaluation gate
   that escalates upon passing the 14-point rubric.
3. ADK harness tools safely read/write workspace files, activate skills from
   harness/skills/, execute pytest/ruff, and record tool trajectory telemetry.
"""

from pathlib import Path
from typing import Any

import pytest
from google.adk.agents import Agent, BaseAgent, LoopAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agents.baselines import (
    _apply_harnessed_self_healing_iteration_2,
    _write_harnessed_iteration_1,
)
from app.agents.harnessed import (
    RubricEvaluationGateAgent,
    create_builder_agent,
    create_harness_loop_agent,
)
from app.agents.tools import (
    HARNESS_TOOLS,
    activate_skill,
    read_workspace_file,
    run_pytest,
    run_ruff_check,
    write_workspace_file,
)
from app.agents.unharnessed import create_unharnessed_agent
from app.config import DEFAULT_MODEL, load_harness_context


class _StubToolContext:
    """Minimal ToolContext stub for unit-testing ADK tool functions directly."""

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state


def test_unharnessed_agent_is_bare_adk_agent() -> None:
    """Verify Track 1 creates a bare ADK Agent with no persona, context, or tools."""
    agent = create_unharnessed_agent(model=DEFAULT_MODEL)
    assert isinstance(agent, Agent)
    assert agent.name == "unharnessed_vibe_agent"
    assert agent.instruction == ""
    assert len(agent.tools) == 0


def test_harnessed_loop_agent_structure() -> None:
    """Verify Track 2 creates an ADK LoopAgent with builder LlmAgent and RubricEvaluationGateAgent."""
    loop_agent = create_harness_loop_agent(model=DEFAULT_MODEL, max_iterations=5)
    assert isinstance(loop_agent, LoopAgent)
    assert loop_agent.name == "harness_engineering_loop"
    assert loop_agent.max_iterations == 5
    assert len(loop_agent.sub_agents) == 2

    builder, gate = loop_agent.sub_agents
    assert isinstance(builder, Agent)
    assert builder.name == "harnessed_builder_agent"
    assert len(builder.tools) == len(HARNESS_TOOLS)

    assert isinstance(gate, RubricEvaluationGateAgent)
    assert isinstance(gate, BaseAgent)
    assert gate.name == "rubric_evaluation_gate"


def test_builder_instruction_provider_uses_external_harness_context() -> None:
    """Verify builder instruction provider injects harness_context.md and living memory diagnostics."""
    builder = create_builder_agent(model=DEFAULT_MODEL)
    assert callable(builder.instruction)

    class _DummyReadonlyContext:
        def __init__(self, state: dict[str, Any]) -> None:
            self.state = state

    harness_ctx = load_harness_context()
    assert "game_engine.py" not in harness_ctx
    assert "trivia_service.py" not in harness_ctx
    ctx_iter1 = _DummyReadonlyContext(
        state={
            "harness_context": harness_ctx,
            "living_memory_feedback": "",
        }
    )
    rendered_iter1 = builder.instruction(ctx_iter1)  # type: ignore[arg-type]
    assert isinstance(rendered_iter1, str)
    assert "Principal Software Engineer" in rendered_iter1
    assert "Strict PEP 585" in rendered_iter1
    assert "<available_skills>" in rendered_iter1
    assert "LIVING MEMORY DIAGNOSTICS" not in rendered_iter1

    ctx_iter2 = _DummyReadonlyContext(
        state={
            "harness_context": harness_ctx,
            "living_memory_feedback": "- Check 1.6 (Frontend UI Structure & HUD) FAILED: missing modal.",
        }
    )
    rendered_iter2 = builder.instruction(ctx_iter2)  # type: ignore[arg-type]
    assert isinstance(rendered_iter2, str)
    assert "LIVING MEMORY DIAGNOSTICS" in rendered_iter2
    assert "Check 1.6" in rendered_iter2


def test_adk_harness_tools_execution(tmp_path: Path) -> None:
    """Verify ADK FunctionTools operate safely inside workspace and record trajectory."""
    state: dict[str, Any] = {
        "workspace_path": str(tmp_path),
        "activated_skills": [],
        "files_modified_in_iteration": [],
        "tool_trajectory": [],
    }
    ctx = _StubToolContext(state)

    # 1. Activate skill
    skill_res = activate_skill("test-driven-development", ctx)  # type: ignore[arg-type]
    assert skill_res["status"] == "ok"
    assert "RED" in skill_res["instructions"]
    assert "test-driven-development" in state["activated_skills"]

    # 1b. Guard against running pytest/ruff on an empty workspace
    empty_pytest = run_pytest(ctx)  # type: ignore[arg-type]
    assert empty_pytest["status"] == "skipped"
    empty_ruff = run_ruff_check(ctx)  # type: ignore[arg-type]
    assert empty_ruff["status"] == "skipped"

    # 2. Write and read workspace file
    write_res = write_workspace_file(
        "tests/test_sample.py",
        "def test_math() -> None:\n    assert 1 + 1 == 2\n",
        ctx,  # type: ignore[arg-type]
    )
    assert write_res["status"] == "ok"
    assert "tests/test_sample.py" in state["files_modified_in_iteration"]

    read_res = read_workspace_file("tests/test_sample.py", ctx)  # type: ignore[arg-type]
    assert read_res["status"] == "ok"
    assert "assert 1 + 1 == 2" in read_res["content"]

    # 3. Path traversal and directory target rejection
    traversal_res = write_workspace_file("../outside.py", "print(1)", ctx)  # type: ignore[arg-type]
    assert traversal_res["status"] == "error"
    dir_res = write_workspace_file("tests", "print(1)", ctx)  # type: ignore[arg-type]
    assert dir_res["status"] == "error"
    assert "directory" in dir_res["message"]

    # 4. Run pytest and ruff tools
    pytest_res = run_pytest(ctx)  # type: ignore[arg-type]
    assert pytest_res["status"] == "passed"

    ruff_res = run_ruff_check(ctx)  # type: ignore[arg-type]
    assert ruff_res["status"] == "passed"
    assert len(state["tool_trajectory"]) >= 5


@pytest.mark.anyio
async def test_rubric_evaluation_gate_agent_escalation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify RubricEvaluationGateAgent records living memory and escalates when 14/14 checks pass."""
    monkeypatch.setattr("app.rubric.semantic.get_genai_client", lambda: (None, "NONE"))
    ws_dir = tmp_path / "candidate"
    memory_file = tmp_path / "LIVING_MEMORY.md"

    # Populate Iteration 1 (incomplete UI -> fails check 1.6 & 1.7)
    _write_harnessed_iteration_1(ws_dir)

    gate_agent = RubricEvaluationGateAgent(
        name="rubric_evaluation_gate",
        max_iterations=5,
        living_memory_path=memory_file,
    )
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="test_gate_app",
        user_id="test_user",
        session_id="s1",
        state={
            "workspace_path": str(ws_dir),
            "iteration": 0,
            "files_modified_in_iteration": ["game_engine.py", "main.py"],
            "tool_trajectory": [{"tool": "write_workspace_file", "status": "ok"}],
            "score_history": [],
            "living_memory_feedback": "",
        },
    )
    runner = Runner(
        agent=gate_agent,
        app_name="test_gate_app",
        session_service=session_service,
    )

    events_it1 = []
    async for event in runner.run_async(
        user_id="test_user",
        session_id="s1",
        new_message=types.Content(role="user", parts=[types.Part.from_text(text="Evaluate Iteration 1")]),
    ):
        events_it1.append(event)

    assert len(events_it1) == 1
    evt1 = events_it1[0]
    assert not evt1.actions.escalate
    assert evt1.custom_metadata is not None
    assert evt1.custom_metadata["iteration"] == 1
    assert evt1.custom_metadata["scorecard"]["is_passing"] is False

    # Now apply Iteration 2 self-healing so workspace achieves 14/14
    _apply_harnessed_self_healing_iteration_2(ws_dir)

    events_it2 = []
    async for event in runner.run_async(
        user_id="test_user",
        session_id="s1",
        new_message=types.Content(role="user", parts=[types.Part.from_text(text="Evaluate Iteration 2")]),
    ):
        events_it2.append(event)

    assert len(events_it2) == 1
    evt2 = events_it2[0]
    assert evt2.actions.escalate is True
    assert evt2.custom_metadata is not None
    assert evt2.custom_metadata["iteration"] == 2
    assert evt2.custom_metadata["scorecard"]["is_passing"] is True
    assert memory_file.is_file()
    mem_text = memory_file.read_text(encoding="utf-8")
    assert "Iteration 1" in mem_text
    assert "Iteration 2" in mem_text

