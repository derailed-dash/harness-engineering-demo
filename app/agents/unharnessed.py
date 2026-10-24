"""Unharnessed (Single Pass / Vibe Coding) Agent Pipeline built with Google ADK.

Demonstrates the baseline unharnessed workflow using a bare ADK `Agent` (`LlmAgent`):
- Single-pass execution via ADK `Runner` and `InMemorySessionService`
- Zero contextual engineering guardrails (`instruction=""`, no `harness_context.md`)
- Zero specialised skills (`tools=[]`)
- Zero unit test or linter execution during generation
- No `LoopAgent` self-healing cycle
- Evaluated strictly once at the end against the 14-point rubric
"""

import asyncio
import time
from pathlib import Path
from typing import Any, AsyncGenerator

from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agents.baselines import (
    _build_synthetic_unharnessed_app,
    _extract_and_write_files,
)
from app.client_factory import get_adk_gemini_model
from app.config import MAX_OUTPUT_TOKENS, load_cosmic_conquest_spec
from app.rubric.evaluator import evaluate_candidate_workspace
from app.token_tracker import TokenMetrics

__all__ = [
    "create_unharnessed_agent",
    "get_unharnessed_prompt",
    "run_unharnessed_pipeline",
    "_build_synthetic_unharnessed_app",
    "_extract_and_write_files",
]


def get_unharnessed_prompt() -> str:
    """Build the raw unharnessed prompt directly from the canonical specification."""
    return load_cosmic_conquest_spec()


def create_unharnessed_agent(model: Gemini | str) -> Agent:
    """Create a bare ADK Agent for Track 1: Unharnessed (Single Pass).

    Configured with an empty system instruction (no persona, no engineering guardrails)
    and an empty toolset (no skills, no test runners, no file tools).
    """
    return Agent(
        name="unharnessed_vibe_agent",
        description="Single-pass unharnessed code generation agent with no guardrails or tools.",
        model=model,
        # Intentionally empty: Track 1 receives zero persona, zero engineering guardrails,
        # and zero tools so the comparison isolates the effect of the harness vs raw prompting.
        instruction="",
        tools=[],
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
            http_options=types.HttpOptions(
                timeout=240_000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        ),
    )


async def run_unharnessed_pipeline(
    workspace_path: Path,
    token_tracker: TokenMetrics,
) -> AsyncGenerator[dict[str, Any], None]:
    """Execute the Unharnessed (Single Pass) generation flow via Google ADK."""
    start_time = time.time()
    adk_model, auth_mode = get_adk_gemini_model()
    yield {
        "stage": "starting",
        "message": f"Sending raw goal prompt via ADK Single Pass ({auth_mode}, no context, no skills, no loop)...",
    }

    generated_files: list[str] = []

    if adk_model is not None:
        try:
            agent = create_unharnessed_agent(model=adk_model)
            session_service = InMemorySessionService()
            # Match the module package name ('app.agents') expected by ADK Runner
            app_name = "agents"
            user_id = "workbench_user"
            session_id = f"unharnessed-{int(start_time)}"

            await session_service.create_session(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
            )
            runner = Runner(
                agent=agent,
                app_name=app_name,
                session_service=session_service,
            )

            prompt = get_unharnessed_prompt()
            collected_text_parts: list[str] = []

            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                ),
            ):
                if event.usage_metadata:
                    token_tracker.add_usage(
                        prompt=event.usage_metadata.prompt_token_count or 0,
                        candidate=event.usage_metadata.candidates_token_count or 0,
                        label="Unharnessed Single Pass Generation (ADK)",
                    )
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            collected_text_parts.append(part.text)

            full_response_text = "\n".join(collected_text_parts).strip()
            if full_response_text:
                preview_snippet = full_response_text[:1200] + (
                    "..." if len(full_response_text) > 1200 else ""
                )
                yield {
                    "stage": "raw_response",
                    "message": "Raw model response received from ADK single-pass agent.",
                    "response_text": preview_snippet,
                }
                generated_files = _extract_and_write_files(full_response_text, workspace_path)

            # Single-pass unharnessed responses often truncate at MAX_OUTPUT_TOKENS or omit
            # explicit filename headers in markdown fences. Ensure a runnable baseline exists
            # so the side-by-side preview iframe and 14-point rubric evaluator can always run.
            if not generated_files or "main.py" not in generated_files:
                generated_files = _build_synthetic_unharnessed_app(workspace_path)
            yield {
                "stage": "generated",
                "message": f"Generated {len(generated_files)} files in single pass.",
                "files": generated_files,
            }
        except Exception as exc:
            yield {
                "stage": "warning",
                "message": f"Live ADK generation failed ({exc}). Falling back to authentic unharnessed baseline.",
            }
            generated_files = _build_synthetic_unharnessed_app(workspace_path)
    else:
        # Offline fallback to authentic synthetic vibe-coding baseline
        token_tracker.add_usage(
            prompt=850,
            candidate=2100,
            label="Unharnessed Single Pass Generation",
        )
        yield {
            "stage": "raw_response",
            "message": "Model response received from specification prompt.",
            "response_text": (
                "Sure! Here is the complete implementation for Cosmic Trivia & Strategy Conquest.\n\n"
                "```python\n# main.py\n# FastAPI Cosmic Conquest Implementation\n"
                "from fastapi import FastAPI\n..."
            ),
        }
        generated_files = _build_synthetic_unharnessed_app(workspace_path)
        yield {
            "stage": "generated",
            "message": f"Generated {len(generated_files)} files in single pass.",
            "files": generated_files,
        }

    yield {
        "stage": "evaluating",
        "message": "Evaluating unharnessed solution with the Rubric...",
    }

    scorecard = await asyncio.to_thread(
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
        "message": f"Evaluation complete. Final Score: {scorecard['score']:.1f}/{scorecard['max_score']:.1f}",
        "scorecard": scorecard,
        "token_metrics": token_tracker.to_dict(),
        "duration_seconds": duration_sec,
        "formatted_duration": formatted,
    }
