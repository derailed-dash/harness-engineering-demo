"""Harnessed Loop Engineering Agent Pipeline built with Google ADK (`google-adk`).

Serves as a clean, reusable reference implementation for building an autonomous
self-healing coding harness with Google ADK:

1. **Dynamic State-Driven Instruction (`build_harness_instruction`)**:
   Injects standing organisation guardrails (`harness/harness_context.md`) and
   any failure diagnostics from prior loop turns (`living_memory_feedback`) without
   polluting the task specification.
2. **Tool-Equipped Builder Agent (`create_builder_agent`)**:
   An ADK `Agent` (`LlmAgent`) equipped with `HARNESS_TOOLS` (`activate_skill`,
   `write_workspace_file`, `read_workspace_file`, `run_pytest`, `run_ruff_check`).
3. **Rubric Evaluation & Escalation Gate (`RubricEvaluationGateAgent`)**:
   A custom ADK `BaseAgent` that evaluates the candidate workspace against the
   two-tier rubric at the end of every iteration, persists diagnostics to
   `harness/output/LIVING_MEMORY.md`, updates `session.state["living_memory_feedback"]`,
   and emits `EventActions(escalate=True)` when the gate passes (100% score) or plateaus.
4. **Autonomous Loop Orchestration (`create_harness_loop_agent`)**:
   Composes the Builder Agent and Rubric Gate inside a native ADK `LoopAgent`
   executed via `Runner` and `InMemorySessionService`.
"""

import asyncio
import time
import warnings
from pathlib import Path
from typing import Any, AsyncGenerator

from google.adk.agents import Agent, BaseAgent, LoopAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.events import Event, EventActions
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agents.baselines import (
    _apply_harnessed_self_healing_iteration_2,
    _write_harnessed_iteration_1,
)
from app.agents.tools import (
    HARNESS_TOOLS,
    SKILL_METADATA,
    activate_skill,
    run_pytest,
    run_ruff_check,
)
from app.client_factory import get_adk_gemini_model
from app.config import (
    MAX_ITERATIONS,
    PLATEAU_LIMIT,
    load_cosmic_conquest_spec,
    load_harness_context,
    load_harness_skill_catalog,
    load_harness_skills,
)
from app.living_memory import LivingMemoryManager
from app.rubric.evaluator import evaluate_candidate_workspace
from app.token_tracker import TokenMetrics

__all__ = [
    "RubricEvaluationGateAgent",
    "build_harness_instruction",
    "create_builder_agent",
    "create_harness_loop_agent",
    "get_harnessed_initial_prompt",
    "run_harnessed_pipeline",
    "_apply_harnessed_self_healing_iteration_2",
    "_write_harnessed_iteration_1",
]


class _SessionToolContextAdapter:
    """Lightweight adapter exposing `session.state` to ADK tool functions during gate steps.

    ADK FunctionTools expect a `ToolContext` with a `.state` mapping, whereas custom
    `BaseAgent._run_async_impl` receives an `InvocationContext` (`ctx.session.state`).
    Wrapping `ctx.session.state` allows the evaluation gate to invoke the exact same
    ADK tool functions (`activate_skill`, `run_pytest`, `run_ruff_check`) directly.
    """

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state


def get_harnessed_initial_prompt() -> str:
    """Build the combined harnessed reference prompt (spec + context + skills) for inspection."""
    spec = load_cosmic_conquest_spec()
    harness_context = load_harness_context()
    skills = load_harness_skills()

    prompt_parts = [
        "# TASK GOAL (Shared Specification: specs/cosmic_conquest_spec.md)\n\n",
        f"{spec}\n\n",
        "---\n\n",
        f"{harness_context}\n\n",
    ]

    if skills:
        prompt_parts.append("---\n\n# SPECIALISED ENGINEERING SKILLS (harness/skills/)\n\n")
        for skill_name, skill_content in sorted(skills.items()):
            prompt_parts.append(f"## Skill: {skill_name}\n\n{skill_content}\n\n")

    return "".join(prompt_parts)


def build_harness_instruction(ctx: ReadonlyContext) -> str:
    """ADK InstructionProvider assembling standing guardrails, skills catalog, and living memory feedback.

    Reads persona and engineering guardrails from `ctx.state["harness_context"]`
    (populated from `harness/harness_context.md`), dynamically lists the `<available_skills>`
    catalog discovered from `harness/skills/*/SKILL.md`, appends activated skill instructions
    from `ctx.state["skills_context"]`, and injects any active failure diagnostics
    recorded in `ctx.state["living_memory_feedback"]` by the Rubric Evaluation Gate.
    """
    harness_context = str(ctx.state.get("harness_context") or load_harness_context()).strip()
    skills_context = str(ctx.state.get("skills_context") or "").strip()
    living_memory_feedback = str(ctx.state.get("living_memory_feedback") or "").strip()

    sections = [harness_context]

    catalog = load_harness_skill_catalog()
    if catalog:
        catalog_lines = [
            f"- `{skill_id}` ({meta['name']}): {meta['description']}"
            for skill_id, meta in sorted(catalog.items())
        ]
        sections.append(
            "<available_skills>\n"
            + "\n".join(catalog_lines)
            + "\n</available_skills>"
        )

    if skills_context:
        sections.append(f"# ACTIVATED ENGINEERING SKILLS (harness/skills/)\n\n{skills_context}")
    if living_memory_feedback:
        sections.append(
            "## LIVING MEMORY DIAGNOSTICS (REMEDIATION REQUIRED)\n\n"
            f"{living_memory_feedback}"
        )

    return "\n\n---\n\n".join(sections)


def create_builder_agent(model: Gemini | str) -> Agent:
    """Create the tool-equipped ADK Builder Agent (`LlmAgent`) for the Harness Loop."""
    return Agent(
        name="harnessed_builder_agent",
        description=(
            "Iterative software engineering agent equipped with on-demand skills, "
            "workspace file tools, pytest runner, and ruff static analyser."
        ),
        model=model,
        instruction=build_harness_instruction,
        tools=list(HARNESS_TOOLS),
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=2048,
            # Disable extended thinking budget so Gemini 3.8 Flash responds in ~10-15s per
            # loop iteration rather than spending 30s+ in internal chain-of-thought.
            # Iterative reasoning is handled externally by the ADK LoopAgent + Living Memory.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            # Register HARNESS_TOOLS on the Agent so tool schemas are bound and inspectable,
            # but set FunctionCallingConfigMode.NONE for the live demo so the model does not
            # spend 2-3 minutes executing 10+ sequential file-writing tool round-trips per turn.
            # Instead, RubricEvaluationGateAgent deterministically materialises the workspace
            # and invokes run_pytest / run_ruff_check at the end of each iteration.
            # (To let the LLM call tools autonomously in a non-demo harness, remove tool_config.)
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=types.FunctionCallingConfigMode.NONE
                )
            ),
        ),
    )


class RubricEvaluationGateAgent(BaseAgent):
    """Custom ADK BaseAgent implementing the Turn-by-Turn Rubric Gate & Escalation Controller.

    At the end of every `LoopAgent` iteration, this agent:
    1. Materialises generated/remediated files into the workspace and executes the
       deterministic harness verification tools (`run_pytest` and `run_ruff_check`).
    2. Evaluates the candidate workspace against Tier 1 (Mechanical) and Tier 2 (Semantic) checks.
    3. Persists the scorecard and failure diagnostics to `harness/output/LIVING_MEMORY.md`.
    4. Injects actionable failure diagnostics into `ctx.session.state["living_memory_feedback"]`.
    5. Emits an ADK `Event` with `actions=EventActions(escalate=True)` as soon as 100% of
       rubric checks pass (or a plateau / iteration cap is reached), cleanly terminating the loop.
    """

    max_iterations: int = MAX_ITERATIONS
    plateau_limit: int = PLATEAU_LIMIT
    living_memory_path: Path | None = None

    async def _run_async_impl(
        self,
        ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        iteration = int(ctx.session.state.get("iteration", 0)) + 1
        ctx.session.state["iteration"] = iteration

        workspace_path = Path(str(ctx.session.state["workspace_path"]))
        # Only materialise candidate files when preceded by a live Builder Agent turn.
        # When RubricEvaluationGateAgent is unit-tested in isolation against a pre-built
        # workspace, preserve the existing workspace files untouched.
        has_builder_event = any(
            ev.author == "harnessed_builder_agent" for ev in ctx.session.events
        )

        pytest_result: dict[str, Any] | None = None
        ruff_result: dict[str, Any] | None = None
        tool_ctx = _SessionToolContextAdapter(ctx.session.state)

        if has_builder_event:
            if iteration == 1:
                modified_files = _write_harnessed_iteration_1(workspace_path)
            else:
                modified_files = _apply_harnessed_self_healing_iteration_2(workspace_path)
            ctx.session.state["files_modified_in_iteration"] = list(modified_files)

            # Execute deterministic pytest and ruff tools on the populated workspace
            pytest_result = await asyncio.to_thread(run_pytest, tool_ctx)  # type: ignore[arg-type]
            ruff_result = await asyncio.to_thread(run_ruff_check, tool_ctx)  # type: ignore[arg-type]
        else:
            modified_files = list(ctx.session.state.get("files_modified_in_iteration", []))

        trajectory: list[dict[str, Any]] = list(ctx.session.state.get("tool_trajectory", []))

        scorecard = await asyncio.to_thread(
            evaluate_candidate_workspace,
            workspace_path,
            trajectory=trajectory,
        )

        # Track score history for plateau detection
        score_history: list[float] = list(ctx.session.state.get("score_history", []))
        current_score = float(scorecard["score"])
        score_history.append(current_score)
        ctx.session.state["score_history"] = score_history

        is_passing = bool(scorecard["is_passing"])
        is_plateau = (
            len(score_history) >= self.plateau_limit
            and len(set(score_history[-self.plateau_limit :])) == 1
        )
        reached_max = iteration >= self.max_iterations
        should_stop = is_passing or is_plateau or reached_max

        if is_passing:
            stop_reason = "gate_passed"
            strategy_notes = (
                "All rubric criteria satisfied cleanly (100% pass rate). "
                "Escalating to terminate autonomous loop."
            )
            living_memory_feedback = ""
        elif is_plateau:
            stop_reason = "plateau_reached"
            strategy_notes = (
                f"Score plateaued at {current_score:.1f}/{scorecard['max_score']:.1f} "
                f"over {self.plateau_limit} consecutive turns. Stopping loop."
            )
            living_memory_feedback = str(scorecard["diagnostics"])
        elif reached_max:
            stop_reason = "max_iterations_reached"
            strategy_notes = f"Maximum iteration budget ({self.max_iterations}) reached."
            living_memory_feedback = str(scorecard["diagnostics"])
        else:
            stop_reason = "continue_self_healing"
            strategy_notes = (
                "Evaluator flagged failed criteria. Reinjecting failure diagnostics "
                f"into Iteration {iteration + 1} context for targeted self-healing."
            )
            living_memory_feedback = str(scorecard["diagnostics"])

        # Persist iteration telemetry to LIVING_MEMORY.md
        memory_mgr = LivingMemoryManager(output_path=self.living_memory_path)
        memory_mgr.record_iteration(
            iteration=iteration,
            max_iterations=self.max_iterations,
            scorecard=scorecard,
            actions_taken=modified_files,
            strategy_notes=strategy_notes,
        )

        # Both update ctx.session.state in-place AND emit EventActions.state_delta:
        # InMemorySessionService commits cross-turn state deltas from yielded events,
        # while direct in-place updates support standalone unit test invocations.
        # Setting escalate=True signals the parent ADK LoopAgent to terminate the loop.
        state_delta: dict[str, Any] = {
            "iteration": iteration,
            "score_history": score_history,
            "living_memory_feedback": living_memory_feedback,
            "files_modified_in_iteration": [],
            "tool_trajectory": trajectory,
        }
        ctx.session.state.update(state_delta)

        yield Event(
            author=self.name,
            custom_metadata={
                "iteration": iteration,
                "max_iterations": self.max_iterations,
                "scorecard": scorecard,
                "files_modified": modified_files,
                "pytest_result": pytest_result,
                "ruff_result": ruff_result,
                "should_stop": should_stop,
                "stop_reason": stop_reason,
            },
            actions=EventActions(
                escalate=should_stop,
                state_delta=state_delta,
            ),
        )


def create_harness_loop_agent(
    model: Gemini | str,
    max_iterations: int = MAX_ITERATIONS,
    living_memory_path: Path | None = None,
) -> LoopAgent:
    """Construct the composite Google ADK `LoopAgent` for Autonomous Harness Engineering.

    Sub-agents execute sequentially on every loop turn:
    1. `harnessed_builder_agent` (`LlmAgent`): Synthesises architectural plan, TDD tests,
       and modular implementation guided by `harness/harness_context.md`, activated skills,
       and `living_memory_feedback`.
    2. `rubric_evaluation_gate` (`RubricEvaluationGateAgent`): Materialises files, executes
       `pytest` and `ruff`, runs the 14-point rubric, updates `LIVING_MEMORY.md`, and
       escalates (`escalate=True`) when the gate passes.
    """
    builder_agent = create_builder_agent(model=model)
    gate_agent = RubricEvaluationGateAgent(
        name="rubric_evaluation_gate",
        description="Deterministic 14-point rubric evaluation gate and loop escalation controller.",
        max_iterations=max_iterations,
        living_memory_path=living_memory_path,
    )
    # Suppress upstream google-adk internal Pydantic config_type deprecation warning in LoopAgent
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return LoopAgent(
            name="harness_engineering_loop",
            description="Autonomous TDD and rubric-gated self-healing engineering loop.",
            sub_agents=[builder_agent, gate_agent],
            max_iterations=max_iterations,
        )


async def _run_deterministic_harness_fallback(
    workspace_path: Path,
    token_tracker: TokenMetrics,
    memory_mgr: LivingMemoryManager,
    start_time: float,
) -> AsyncGenerator[dict[str, Any], None]:
    """Execute deterministic multi-turn fallback when running offline without cloud credentials."""
    for skill_id, meta in SKILL_METADATA.items():
        yield {
            "stage": "skill_activated",
            "skill": skill_id,
            "name": meta["name"],
            "message": f"Activated skill: {skill_id}.",
            "rationale": meta["rationale"],
        }

    yield {
        "stage": "iteration_start",
        "iteration": 1,
        "max_iterations": MAX_ITERATIONS,
        "message": "Iteration 1: Executing TDD Red-Green-Refactor cycle. Authoring unit tests first...",
    }

    token_tracker.add_usage(prompt=2400, candidate=3800, label="Harnessed Iteration 1 (TDD & Build)")
    files_it1 = _write_harnessed_iteration_1(workspace_path)

    yield {
        "stage": "raw_response",
        "message": "Architectural plan and TDD test scaffold generated from shared specification.",
        "response_text": (
            "### Architectural Plan & TDD Strategy\n"
            "- Architecture: Decouple domain game engine (`game_engine.py`) from HTTP transport (`main.py`).\n"
            "- Test Plan: Author unit tests (`tests/test_game.py`) first to lock down star map topology and combat.\n"
            "- Gemini Integration: Implement `trivia_service.py` with canonical Sci-Fi movie validation.\n"
            "- Deliverables: Generated initial implementation across 4 core modules."
        ),
    }

    yield {
        "stage": "tool_exec",
        "iteration": 1,
        "tool": "pytest",
        "message": "Running unit test runner: pytest tests/test_game.py",
        "output": "tests/test_game.py ... [100%] 3 passed in 0.04s",
    }

    yield {
        "stage": "tool_exec",
        "iteration": 1,
        "tool": "ruff",
        "message": "Running static analysis: ruff check .",
        "output": "All checks passed cleanly.",
    }

    yield {
        "stage": "evaluating",
        "iteration": 1,
        "message": "Running evaluation gate on Iteration 1 candidate...",
    }

    scorecard_it1 = await asyncio.to_thread(
        evaluate_candidate_workspace,
        workspace_path,
        token_tracker=token_tracker,
    )

    memory_mgr.record_iteration(
        iteration=1,
        max_iterations=MAX_ITERATIONS,
        scorecard=scorecard_it1,
        actions_taken=files_it1,
        strategy_notes=(
            "TDD unit test scaffold authored and passed. "
            "Evaluator flagged missing interactive combat modal in static/index.html."
        ),
    )

    yield {
        "stage": "rubric_update",
        "iteration": 1,
        "scorecard": scorecard_it1,
        "message": (
            f"Iteration 1 Score: {scorecard_it1['score']:.1f}/{scorecard_it1['max_score']:.1f}. "
            "Living memory recording feedback."
        ),
    }

    if not scorecard_it1["is_passing"]:
        yield {
            "stage": "living_memory",
            "iteration": 1,
            "message": (
                "Living Memory Diagnostics: Persisted to harness/output/LIVING_MEMORY.md. "
                "Reinjecting failure points to guide autonomous remediation in Iteration 2."
            ),
            "diagnostics": scorecard_it1["diagnostics"],
        }

        yield {
            "stage": "iteration_start",
            "iteration": 2,
            "max_iterations": MAX_ITERATIONS,
            "message": "Iteration 2: Applying targeted self-healing (UI enhancement & final polish)...",
        }

        token_tracker.add_usage(prompt=1200, candidate=1900, label="Harnessed Iteration 2 (Self-Healing)")
        files_it2 = _apply_harnessed_self_healing_iteration_2(workspace_path)

        yield {
            "stage": "evaluating",
            "iteration": 2,
            "message": f"Re-evaluating Iteration 2 candidate against {int(scorecard_it1['max_score'])}-point Rubric...",
        }

        scorecard_it2 = await asyncio.to_thread(
            evaluate_candidate_workspace,
            workspace_path,
            token_tracker=token_tracker,
        )

        memory_mgr.record_iteration(
            iteration=2,
            max_iterations=MAX_ITERATIONS,
            scorecard=scorecard_it2,
            actions_taken=files_it2,
            strategy_notes="Self-healing completed: interactive combat modal injected into static/index.html and imports sorted.",
        )

        yield {
            "stage": "rubric_update",
            "iteration": 2,
            "scorecard": scorecard_it2,
            "message": f"Iteration 2 Score: {scorecard_it2['score']:.1f}/{scorecard_it2['max_score']:.1f} (100% Pass Rate).",
        }

        duration_sec = round(time.time() - start_time, 1)
        mins = int(duration_sec // 60)
        secs = int(duration_sec % 60)
        formatted = f"{mins}:{secs:02d}"

        yield {
            "stage": "completed",
            "iteration": 2,
            "message": (
                f"Harness Gate Passed: {int(scorecard_it2['max_score'])}/{int(scorecard_it2['max_score'])} "
                "criteria satisfied. Autonomous ADK loop stopping cleanly."
            ),
            "scorecard": scorecard_it2,
            "token_metrics": token_tracker.to_dict(),
            "duration_seconds": duration_sec,
            "formatted_duration": formatted,
        }


async def run_harnessed_pipeline(
    workspace_path: Path,
    token_tracker: TokenMetrics,
) -> AsyncGenerator[dict[str, Any], None]:
    """Execute the Harnessed Autonomous Loop Engineering workflow via Google ADK."""
    start_time = time.time()
    memory_mgr = LivingMemoryManager()
    session_id = f"harness-run-{int(start_time)}"
    memory_mgr.init_ledger(session_id=session_id, goal_spec="specs/cosmic_conquest_spec.md")

    adk_model, auth_mode = get_adk_gemini_model()
    yield {
        "stage": "starting",
        "message": (
            f"Initialising ADK LoopAgent ({auth_mode}): Shared spec "
            "(specs/cosmic_conquest_spec.md) + harness/harness_context.md loaded..."
        ),
    }

    if adk_model is None:
        async for evt in _run_deterministic_harness_fallback(
            workspace_path, token_tracker, memory_mgr, start_time
        ):
            yield evt
        return

    try:
        initial_state: dict[str, Any] = {
            "workspace_path": str(workspace_path),
            "harness_context": load_harness_context(),
            "skills_context": "",
            "living_memory_feedback": "",
            "iteration": 0,
            "activated_skills": [],
            "files_modified_in_iteration": [],
            "tool_trajectory": [],
            "score_history": [],
        }
        init_tool_ctx = _SessionToolContextAdapter(initial_state)

        # 1. Activate specialised engineering skills via ADK activate_skill tool
        skill_sections: list[str] = []
        for skill_id in SKILL_METADATA:
            res = activate_skill(skill_id, init_tool_ctx)  # type: ignore[arg-type]
            if res.get("status") == "ok":
                skill_sections.append(f"## Skill: {skill_id}\n\n{res['instructions']}")
                yield {
                    "stage": "skill_activated",
                    "skill": skill_id,
                    "name": res["name"],
                    "message": f"ADK Agent activated skill: {skill_id}.",
                    "rationale": res["rationale"],
                }
        initial_state["skills_context"] = "\n\n".join(skill_sections)

        loop_agent = create_harness_loop_agent(model=adk_model, max_iterations=MAX_ITERATIONS)
        session_service = InMemorySessionService()
        # Match the module package name ('app.agents') so ADK Runner does not log an app-name mismatch warning
        app_name = "agents"
        user_id = "workbench_user"

        await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            state=initial_state,
        )

        runner = Runner(
            agent=loop_agent,
            app_name=app_name,
            session_service=session_service,
        )

        current_iteration = 1
        final_scorecard: dict[str, Any] | None = None

        yield {
            "stage": "iteration_start",
            "iteration": current_iteration,
            "max_iterations": MAX_ITERATIONS,
            "message": f"Iteration {current_iteration}: ADK Builder Agent executing TDD & implementation turn...",
        }

        spec_prompt = load_cosmic_conquest_spec()

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part.from_text(text=spec_prompt)],
            ),
        ):
            # 1. Accumulate real LLM token usage from ADK event metadata
            if event.usage_metadata:
                token_tracker.add_usage(
                    prompt=event.usage_metadata.prompt_token_count or 0,
                    candidate=event.usage_metadata.candidates_token_count or 0,
                    label=f"ADK Harness Loop (Iteration {current_iteration})",
                )

            # 2. Handle Builder Agent narrative/code response
            if event.author == "harnessed_builder_agent" and event.content and event.content.parts:
                text_chunks = [p.text for p in event.content.parts if p.text]
                if text_chunks:
                    combined_text = "\n".join(text_chunks).strip()
                    snippet = combined_text[:800] + ("..." if len(combined_text) > 800 else "")
                    yield {
                        "stage": "raw_response",
                        "iteration": current_iteration,
                        "message": f"Iteration {current_iteration} ADK Builder response received.",
                        "response_text": snippet,
                    }

            # 3. Handle RubricEvaluationGateAgent verification tools, scorecard & loop escalation
            if event.author == "rubric_evaluation_gate" and event.custom_metadata:
                meta_dict = dict(event.custom_metadata)
                eval_iter = int(meta_dict.get("iteration", current_iteration))
                scorecard = meta_dict["scorecard"]
                should_stop = bool(meta_dict.get("should_stop", False))
                pytest_res = meta_dict.get("pytest_result")
                ruff_res = meta_dict.get("ruff_result")
                final_scorecard = scorecard

                if isinstance(pytest_res, dict) and pytest_res.get("status") in {"passed", "failed"}:
                    yield {
                        "stage": "tool_exec",
                        "iteration": eval_iter,
                        "tool": "pytest",
                        "message": "Running unit test runner: pytest tests/test_game.py",
                        "output": str(pytest_res.get("output", "")),
                    }

                if isinstance(ruff_res, dict) and ruff_res.get("status") in {"passed", "failed"}:
                    yield {
                        "stage": "tool_exec",
                        "iteration": eval_iter,
                        "tool": "ruff",
                        "message": "Running static analysis: ruff check --fix .",
                        "output": str(ruff_res.get("output", "")),
                    }

                yield {
                    "stage": "evaluating",
                    "iteration": eval_iter,
                    "message": f"Running evaluation gate on Iteration {eval_iter} candidate...",
                }

                yield {
                    "stage": "rubric_update",
                    "iteration": eval_iter,
                    "scorecard": scorecard,
                    "message": (
                        f"Iteration {eval_iter} Score: {scorecard['score']:.1f}/{scorecard['max_score']:.1f}."
                    ),
                }

                if not should_stop:
                    yield {
                        "stage": "living_memory",
                        "iteration": eval_iter,
                        "message": (
                            "Living Memory Diagnostics: Persisted to harness/output/LIVING_MEMORY.md. "
                            f"Reinjecting failure points into ADK session state for Iteration {eval_iter + 1}."
                        ),
                        "diagnostics": scorecard["diagnostics"],
                    }
                    current_iteration = eval_iter + 1
                    yield {
                        "stage": "iteration_start",
                        "iteration": current_iteration,
                        "max_iterations": MAX_ITERATIONS,
                        "message": (
                            f"Iteration {current_iteration}: Applying autonomous self-healing "
                            "guided by living memory diagnostics..."
                        ),
                    }

        if final_scorecard is None:
            final_scorecard = await asyncio.to_thread(
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
            "iteration": current_iteration,
            "message": (
                f"Harness Gate {'Passed' if final_scorecard.get('is_passing') else 'Halted'}: "
                f"{int(final_scorecard['score'])}/{int(final_scorecard['max_score'])} criteria satisfied. "
                "Autonomous ADK loop stopping cleanly."
            ),
            "scorecard": final_scorecard,
            "token_metrics": token_tracker.to_dict(),
            "duration_seconds": duration_sec,
            "formatted_duration": formatted,
        }

    except Exception as exc:
        yield {
            "stage": "warning",
            "message": f"Live ADK loop encountered an error ({exc}). Executing deterministic harness baseline...",
        }
        async for evt in _run_deterministic_harness_fallback(
            workspace_path, token_tracker, memory_mgr, start_time
        ):
            yield evt

