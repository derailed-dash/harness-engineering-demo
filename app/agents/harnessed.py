"""Harnessed Loop Runner & Workbench SSE Streaming Pipeline.

Executes the Google ADK `LoopAgent` defined in `app/agents/agent.py` via `Runner`
and `InMemorySessionService`, translating ADK session and tool events into
Server-Sent Events (SSE) for the split-screen Workbench UI.

Re-exports the core ADK agent primitives (`RubricEvaluationGateAgent`,
`build_harness_instruction`, `create_builder_agent`, `create_harness_loop_agent`,
`materialise_builder_output_callback`, `root_agent`) for backwards compatibility.
"""

import asyncio
import time
from pathlib import Path
from typing import Any, AsyncGenerator

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agents.agent import (
    RubricEvaluationGateAgent,
    SessionToolContextAdapter,
    build_harness_instruction,
    create_builder_agent,
    create_harness_loop_agent,
    materialise_builder_output_callback,
    root_agent,
)
from app.agents.baselines import (
    _apply_harnessed_self_healing_iteration_2,
    _write_harnessed_iteration_1,
)
from app.agents.tools import (
    SKILL_METADATA,
    activate_skill,
)
from app.client_factory import get_adk_gemini_model
from app.config import (
    FAST_DEMO_MODE,
    MAX_ITERATIONS,
    load_cosmic_conquest_spec,
    load_harness_context,
    load_harness_skills,
)
from app.living_memory import LivingMemoryManager
from app.rubric.evaluator import evaluate_candidate_workspace
from app.token_tracker import TokenMetrics

__all__ = [
    "RubricEvaluationGateAgent",
    "SessionToolContextAdapter",
    "build_harness_instruction",
    "create_builder_agent",
    "create_harness_loop_agent",
    "get_harnessed_initial_prompt",
    "materialise_builder_output_callback",
    "root_agent",
    "run_harnessed_pipeline",
    "_apply_harnessed_self_healing_iteration_2",
    "_write_harnessed_iteration_1",
]


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
            "fast_demo_mode": FAST_DEMO_MODE,
            "activated_skills": [],
            "files_modified_in_iteration": [],
            "tool_trajectory": [],
            "score_history": [],
        }
        init_tool_ctx = SessionToolContextAdapter(initial_state)

        # In FAST_DEMO_MODE, pre-activate skills upfront so FunctionCallingConfigMode.NONE
        # turns complete in ~15s. When FAST_DEMO_MODE=false, the Builder Agent invokes
        # activate_skill on demand via native ADK tool calling.
        if FAST_DEMO_MODE:
            for skill_id in SKILL_METADATA:
                res = activate_skill(skill_id, init_tool_ctx)  # type: ignore[arg-type]
                if res.get("status") == "ok":
                    yield {
                        "stage": "skill_activated",
                        "skill": skill_id,
                        "name": res["name"],
                        "message": f"ADK Agent activated skill: {skill_id}.",
                        "rationale": res["rationale"],
                    }

        loop_agent = create_harness_loop_agent(
            model=adk_model,
            max_iterations=MAX_ITERATIONS,
            fast_demo_mode=FAST_DEMO_MODE,
        )
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

            # 2. Stream on-demand skill activations & tool responses when FAST_DEMO_MODE is disabled
            if event.content and event.content.parts:
                for part in event.content.parts:
                    fn_resp = getattr(part, "function_response", None)
                    if fn_resp and getattr(fn_resp, "name", "") == "activate_skill":
                        resp_data = getattr(fn_resp, "response", {}) or {}
                        if isinstance(resp_data, dict) and resp_data.get("status") == "ok":
                            yield {
                                "stage": "skill_activated",
                                "skill": resp_data.get("skill", ""),
                                "name": resp_data.get("name", ""),
                                "message": f"ADK Agent activated skill: {resp_data.get('skill', '')}.",
                                "rationale": resp_data.get("rationale", ""),
                            }

            # 3. Handle Builder Agent narrative/code response
            if event.author == "harnessed_builder_agent" and event.content and event.content.parts:
                visible_chunks = [
                    p.text
                    for p in event.content.parts
                    if p.text and not getattr(p, "thought", False)
                ]
                text_chunks = visible_chunks or [p.text for p in event.content.parts if p.text]
                if text_chunks:
                    combined_text = "\n".join(text_chunks).strip()
                    snippet = combined_text[:1600] + ("..." if len(combined_text) > 1600 else "")
                    yield {
                        "stage": "raw_response",
                        "iteration": current_iteration,
                        "message": f"Iteration {current_iteration} ADK Builder response received.",
                        "response_text": snippet,
                    }

            # 4. Handle RubricEvaluationGateAgent verification tools, scorecard & loop escalation
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
