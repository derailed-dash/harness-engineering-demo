"""Google ADK (`google-adk`) Reference Agent Definitions for Autonomous Harness Engineering.

Provides the clean, reusable ADK agent primitives that power the Harnessed Loop:
1. **Dynamic State-Driven Instruction (`build_harness_instruction`)**:
   Injects standing organisation guardrails (`harness/harness_context.md`),
   the `<available_skills>` catalogue (`harness/skills/*/SKILL.md`), activated skill
   instructions (`skills_context`), and any failure diagnostics from prior loop
   turns (`living_memory_feedback`) without polluting the task specification.
2. **Builder Post-Turn Callback (`materialise_builder_output_callback`)**:
   An ADK `after_agent_callback` attached to `harnessed_builder_agent` that
   materialises generated code into the candidate workspace (`_extract_and_write_files`
   or the fast demo baseline when `FAST_DEMO_MODE=true`), leaving the evaluation
   gate 100% decoupled from file creation.
3. **Tool-Equipped Builder Agent (`create_builder_agent`)**:
   An ADK `Agent` (`LlmAgent`) equipped with `HARNESS_TOOLS` (`activate_skill`,
   `write_workspace_file`, `read_workspace_file`, `run_pytest`, `run_ruff_check`).
4. **Pure Rubric Evaluation & Escalation Gate (`RubricEvaluationGateAgent`)**:
   A custom ADK `BaseAgent` that runs `pytest`, `ruff`, and the 14-point rubric
   evaluator at the end of every iteration, persists diagnostics to
   `harness/output/LIVING_MEMORY.md`, updates `session.state["living_memory_feedback"]`,
   and emits `EventActions(escalate=True)` as soon as the gate passes or plateaus.
5. **Composite Loop Orchestration (`create_harness_loop_agent` & `root_agent`)**:
   Composes the Builder Agent and Rubric Gate inside a native ADK `LoopAgent`
   and exposes a module-level `root_agent` compatible with standard ADK CLI
   commands (`adk web`, `adk run`, `adk eval`).
"""

import asyncio
import warnings
from pathlib import Path
from typing import Any, AsyncGenerator

from google.adk.agents import Agent, BaseAgent, LoopAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.events import Event, EventActions
from google.adk.models import Gemini
from google.genai import types

from app.agents.baselines import (
    _apply_harnessed_self_healing_iteration_2,
    _extract_and_write_files,
    _write_harnessed_iteration_1,
)
from app.agents.tools import (
    HARNESS_TOOLS,
    run_pytest,
    run_ruff_check,
)
from app.client_factory import get_adk_gemini_model
from app.config import (
    DEFAULT_MODEL,
    FAST_DEMO_MODE,
    MAX_ITERATIONS,
    PLATEAU_LIMIT,
    load_harness_context,
    load_harness_skill_catalog,
)
from app.living_memory import LivingMemoryManager
from app.rubric.evaluator import evaluate_candidate_workspace

__all__ = [
    "RubricEvaluationGateAgent",
    "SessionToolContextAdapter",
    "build_harness_instruction",
    "create_builder_agent",
    "create_harness_loop_agent",
    "materialise_builder_output_callback",
    "root_agent",
]


class SessionToolContextAdapter:
    """Lightweight adapter exposing `session.state` to ADK tool functions during gate steps.

    ADK FunctionTools expect a `ToolContext` with a `.state` mapping, whereas custom
    `BaseAgent._run_async_impl` receives an `InvocationContext` (`ctx.session.state`).
    Wrapping `ctx.session.state` allows the evaluation gate to invoke the exact same
    ADK tool functions (`activate_skill`, `run_pytest`, `run_ruff_check`) directly.
    """

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state


def build_harness_instruction(ctx: ReadonlyContext) -> str:
    """ADK InstructionProvider assembling standing guardrails, skills catalogue, and living memory feedback.

    Reads persona and engineering guardrails from `ctx.state["harness_context"]`
    (populated from `harness/harness_context.md`), dynamically lists the `<available_skills>`
    catalogue discovered from `harness/skills/*/SKILL.md`, appends activated skill instructions
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


def materialise_builder_output_callback(callback_context: CallbackContext) -> types.Content | None:
    """ADK `after_agent_callback` that materialises builder output into the workspace.

    Decouples workspace file creation from `RubricEvaluationGateAgent`:
    - If the Builder Agent already wrote files via `write_workspace_file` tool calls,
      those files are preserved.
    - When `fast_demo_mode` is active (default for Cloud Run ~15s/turn demo responsiveness),
      materialises the deterministic Iteration 1 TDD scaffold or Iteration 2 self-healing
      remediation into `workspace_path`.
    - Otherwise, parses any fenced `# filename:` blocks emitted in the Builder Agent's
      response and writes them to `workspace_path`.
    """
    raw_ws = callback_context.state.get("workspace_path", "")
    if not raw_ws:
        return None

    workspace_path = Path(str(raw_ws))
    next_iteration = int(callback_context.state.get("iteration", 0)) + 1
    fast_demo = bool(callback_context.state.get("fast_demo_mode", FAST_DEMO_MODE))
    existing_modified = list(callback_context.state.get("files_modified_in_iteration", []))

    if existing_modified:
        return None

    if fast_demo:
        if next_iteration == 1:
            modified_files = _write_harnessed_iteration_1(workspace_path)
        else:
            modified_files = _apply_harnessed_self_healing_iteration_2(workspace_path)
        callback_context.state["files_modified_in_iteration"] = list(modified_files)
        return None

    # Non-demo mode fallback: extract markdown code blocks if model emitted text instead of tool calls
    inv_ctx = getattr(callback_context, "_invocation_context", None)
    if inv_ctx is not None and getattr(inv_ctx, "session", None) is not None:
        text_chunks: list[str] = []
        for ev in reversed(inv_ctx.session.events):
            if ev.author == "harnessed_builder_agent" and ev.content and ev.content.parts:
                for part in ev.content.parts:
                    if part.text:
                        text_chunks.append(part.text)
                break
        if text_chunks:
            extracted = _extract_and_write_files("\n".join(text_chunks), workspace_path)
            if extracted:
                callback_context.state["files_modified_in_iteration"] = list(extracted)

    return None


def create_builder_agent(
    model: Gemini | str,
    fast_demo_mode: bool = FAST_DEMO_MODE,
) -> Agent:
    """Create the tool-equipped ADK Builder Agent (`LlmAgent`) for the Harness Loop.

    Args:
        model: ADK `Gemini` model instance or model name string.
        fast_demo_mode: When True (default for Cloud Run workbench demos), binds
            `HARNESS_TOOLS` schemas for inspection while setting `FunctionCallingConfigMode.NONE`
            so each loop turn completes in ~10-15s via `materialise_builder_output_callback`.
            When False, enables full autonomous LLM tool calling (`activate_skill`,
            `write_workspace_file`, `read_workspace_file`, `run_pytest`, `run_ruff_check`).
    """
    gen_config = types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=2048,
        # Disable extended thinking budget so Gemini 3.8 Flash responds in ~10-15s per
        # loop iteration rather than spending 30s+ in internal chain-of-thought.
        # Iterative reasoning is handled externally by the ADK LoopAgent + Living Memory.
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    if fast_demo_mode:
        gen_config.tool_config = types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode=types.FunctionCallingConfigMode.NONE
            )
        )

    return Agent(
        name="harnessed_builder_agent",
        description=(
            "Iterative software engineering agent equipped with on-demand skills, "
            "workspace file tools, pytest runner, and ruff static analyser."
        ),
        model=model,
        instruction=build_harness_instruction,
        tools=list(HARNESS_TOOLS),
        after_agent_callback=materialise_builder_output_callback,
        generate_content_config=gen_config,
    )


class RubricEvaluationGateAgent(BaseAgent):
    """Pure ADK BaseAgent implementing the Turn-by-Turn Rubric Gate & Escalation Controller.

    At the end of every `LoopAgent` iteration, this agent:
    1. Executes the deterministic harness verification tools (`run_pytest` and `run_ruff_check`)
       against the candidate workspace.
    2. Evaluates the candidate workspace against Tier 1 (Mechanical) and Tier 2 (Semantic) checks.
    3. Persists the scorecard and failure diagnostics to `harness/output/LIVING_MEMORY.md`.
    4. Injects actionable failure diagnostics into `ctx.session.state["living_memory_feedback"]`.
    5. Emits an ADK `Event` with `actions=EventActions(escalate=True)` as soon as 100% of
       rubric checks pass (or a score plateau is reached), cleanly terminating the loop.
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
        has_builder_event = any(
            ev.author == "harnessed_builder_agent" for ev in ctx.session.events
        )

        pytest_result: dict[str, Any] | None = None
        ruff_result: dict[str, Any] | None = None
        tool_ctx = SessionToolContextAdapter(ctx.session.state)

        modified_files = list(ctx.session.state.get("files_modified_in_iteration", []))

        if has_builder_event:
            # Execute deterministic pytest and ruff verification tools on the workspace
            pytest_result = await asyncio.to_thread(run_pytest, tool_ctx)  # type: ignore[arg-type]
            ruff_result = await asyncio.to_thread(run_ruff_check, tool_ctx)  # type: ignore[arg-type]

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
        # Early escalation is triggered when the rubric passes 100% or plateaus;
        # LoopAgent(max_iterations=...) natively enforces the upper iteration bound.
        should_escalate = is_passing or is_plateau
        should_stop = should_escalate or (iteration >= self.max_iterations)

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
        elif iteration >= self.max_iterations:
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
                escalate=should_escalate,
                state_delta=state_delta,
            ),
        )


def create_harness_loop_agent(
    model: Gemini | str,
    max_iterations: int = MAX_ITERATIONS,
    living_memory_path: Path | None = None,
    fast_demo_mode: bool = FAST_DEMO_MODE,
) -> LoopAgent:
    """Construct the composite Google ADK `LoopAgent` for Autonomous Harness Engineering.

    Sub-agents execute sequentially on every loop turn:
    1. `harnessed_builder_agent` (`LlmAgent`): Synthesises architectural plan, TDD tests,
       and modular implementation guided by `harness/harness_context.md`, activated skills,
       and `living_memory_feedback`, then materialises files via `after_agent_callback`.
    2. `rubric_evaluation_gate` (`RubricEvaluationGateAgent`): Executes `pytest` and `ruff`,
       runs the 14-point rubric, updates `LIVING_MEMORY.md`, and escalates (`escalate=True`)
       when the gate passes.
    """
    builder_agent = create_builder_agent(model=model, fast_demo_mode=fast_demo_mode)
    gate_agent = RubricEvaluationGateAgent(
        name="rubric_evaluation_gate",
        description="Deterministic 14-point rubric evaluation gate and loop escalation controller.",
        max_iterations=max_iterations,
        living_memory_path=living_memory_path,
    )
    # Suppress upstream google-adk LoopAgent deprecation notice (Workflow graph nodes
    # require output_schema for conditional routing, which disables FunctionTool calling).
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return LoopAgent(
            name="harness_engineering_loop",
            description="Autonomous TDD and rubric-gated self-healing engineering loop.",
            sub_agents=[builder_agent, gate_agent],
            max_iterations=max_iterations,
        )


def _create_default_root_agent() -> LoopAgent:
    """Initialise the module-level `root_agent` for ADK CLI discovery (`adk web`, `adk run`)."""
    adk_model, _ = get_adk_gemini_model()
    return create_harness_loop_agent(model=adk_model or DEFAULT_MODEL)


root_agent: LoopAgent = _create_default_root_agent()
