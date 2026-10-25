# Cosmic Conquest: Harness Engineering Demo — Task & Session Handover Log

## Completed on Branch `refactor/adk-harness-cleanups`

### 1. Five Architectural Refactorings (`2818a2b`)
- [x] **Extract `SEMANTIC_RUBRIC_PROMPT` into [`harness/RUBRIC.md`](harness/RUBRIC.md) (Single Source of Truth)**:
  - Added `RUBRIC_PATH = HARNESS_DIR / "RUBRIC.md"` and `load_harness_rubric()` in [`app/config.py`](app/config.py).
  - Updated [`app/rubric/semantic.py`](app/rubric/semantic.py) to load criteria `2.1–2.6` dynamically from [`harness/RUBRIC.md`](harness/RUBRIC.md).
  - Added `GET /api/rubric` in [`app/main.py`](app/main.py) and a `RUBRIC` (`harness/RUBRIC.md`) modal button in [`app/templates/index.html`](app/templates/index.html) and [`app/static/js/workbench.js`](app/static/js/workbench.js).
- [x] **Split Pure ADK Agent Definitions ([`app/agents/agent.py`](app/agents/agent.py)) from Runner & SSE Plumbing ([`app/agents/harnessed.py`](app/agents/harnessed.py))**:
  - Extracted `SessionToolContextAdapter`, `build_harness_instruction`, `materialise_builder_output_callback`, `create_builder_agent`, `RubricEvaluationGateAgent`, `create_harness_loop_agent`, and module-level `root_agent` into [`app/agents/agent.py`](app/agents/agent.py) for standard ADK CLI compatibility (`adk web`, `adk run`, `adk eval`).
  - Kept `_run_deterministic_harness_fallback` and `run_harnessed_pipeline` in [`app/agents/harnessed.py`](app/agents/harnessed.py) with backwards-compatible re-exports.
- [x] **Decouple Demo Fixture Materialisation from `RubricEvaluationGateAgent`**:
  - Moved `_write_harnessed_iteration_1` / `_apply_harnessed_self_healing_iteration_2` (and non-demo `# filename:` markdown block extraction) into `materialise_builder_output_callback` (`after_agent_callback` on `harnessed_builder_agent`), leaving `RubricEvaluationGateAgent` a pure evaluation and escalation gate.
- [x] **Support On-Demand Skill Activation & `FAST_DEMO_MODE` Toggle**:
  - Updated `activate_skill` in [`app/agents/tools.py`](app/agents/tools.py) to append activated skill Markdown directly into `tool_context.state["skills_context"]`.
  - Added `FAST_DEMO_MODE` in [`app/config.py`](app/config.py) (`true` by default for Cloud Run ~15s/turn responsiveness; when `false`, enables autonomous LLM tool-calling).
- [x] **Drop Redundant `reached_max` Escalation**:
  - Simplified `RubricEvaluationGateAgent` in [`app/agents/agent.py`](app/agents/agent.py) so `should_escalate = is_passing or is_plateau`, letting `LoopAgent(max_iterations=...)` natively enforce the iteration budget.

### 2. Root-Cause Investigation & Fix for Track 2 Latency Stalls & WSL2 Timeouts
- [x] **Root Cause #1 — `thinking_budget=0` vs `thinking_level=ThinkingLevel.LOW` on `gemini-3.8-flash`**:
  - Per official Gemini 3.8 Flash documentation (`gemini-api-guides/generate-content/thinking.md` and `docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-3-8-flash`), `gemini-3.8-flash` replaces integer `thinking_budget` with `thinking_level` (`LOW`, `MEDIUM` (default), `HIGH`; `MINIMAL` is unsupported and returns HTTP 400).
  - Switched `create_builder_agent` ([`app/agents/agent.py`](app/agents/agent.py)), `create_unharnessed_agent` ([`app/agents/unharnessed.py`](app/agents/unharnessed.py)), and `run_semantic_tier` ([`app/rubric/semantic.py`](app/rubric/semantic.py)) to `types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)`.
- [x] **Root Cause #2 — Default 64K Output Tokens (`MAX_OUTPUT_TOKENS = 65536`) & `X-Server-Timeout` Header**:
  - Restored `MAX_OUTPUT_TOKENS = 65536` in [`app/config.py`](app/config.py) (matching `gemini-3.8-flash`'s 64K SDK default) so single-pass multi-file generation is never prematurely truncated.
  - Because `google-genai` populates the Vertex AI `X-Server-Timeout` HTTP header from `HttpOptions.timeout`, configured `timeout=90_000` (90s) on `unharnessed_vibe_agent` so Vertex AI does not abort Track 1 at 18s with `504 DEADLINE_EXCEEDED`.
- [x] **Root Cause #3 — WSL2 IPv6 Blackholing, Custom `httpx` Transport SSL Context & `tenacity` Retry Amplification**:
  - In [`app/client_factory.py`](app/client_factory.py), `_build_ipv4_http_options()` binds both sync and async `httpx` transports to `local_address="0.0.0.0"` with an explicit `ssl.create_default_context(cafile=certifi.where())`, explicit `httpx.Timeout`, and `retry_options=types.HttpRetryOptions(attempts=1)` (preventing `google-genai`'s default 5-attempt `tenacity` retry loop from multiplying any transient `504` into a multi-minute hang).
- [x] **Root Cause #4 — Semantic Rubric Judge Prompt Slimming (`app/rubric/semantic.py`)**:
  - Stripped `<style>...</style>` CSS blocks from `static/index.html` before sending the candidate codebase to the LLM-as-a-Judge in [`app/rubric/semantic.py`](app/rubric/semantic.py) with a 10s fail-fast timeout and heuristic fallback.
- [x] **Root Cause #5 — Import-Time Client Instantiation & Repeated Cold ADC Lookups**:
  - Updated `_create_default_root_agent()` in [`app/agents/agent.py`](app/agents/agent.py) to pass `model=DEFAULT_MODEL` (`"gemini-3.8-flash"`) rather than instantiating a network client at module import time, and added `_get_cached_adc()` in [`app/client_factory.py`](app/client_factory.py).
- [x] **Verified Live Benchmark Run (`make run`)**:
  - **Track 1 — Unharnessed (Vibe Coding)**: `7.0 / 14.0` score, `1:35` (95s), `2,429` tokens (`$0.0006`).
  - **Track 2 — Harness Engineering with Loop**: `14.0 / 14.0` score (100% Pass Rate in 2 iterations), `0:30` (30s), `8,020` tokens (`$0.0017`).
  - **Combined Pipeline**: Completed in `1:35`, `10,449` total tokens (`$0.0022`).
- [x] **Synchronised Repository Documentation & Blog Series**:
  - Updated [`GEMINI.md`](GEMINI.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`README.md`](README.md), [`harness/harness_context.md`](harness/harness_context.md), and the 4-part blog series in `/home/dazbo/localdev/blogs-and-whitepapers/articles/harness-engineering-with-google/`.
- [x] **Explicit "Save Replay" UI Control & Endpoint (`POST /api/replay/save`)**:
  - Removed automatic replay overwriting at the end of live comparison runs in [`app/orchestrator.py`](app/orchestrator.py) so routine live runs never replace `app/replay/replay_data.json` or `snapshots/`.
  - Cached the latest completed live run in `DemoOrchestrator.last_recorded_events` and added `save_latest_run_as_replay()` + `POST /api/replay/save` in [`app/main.py`](app/main.py).
  - Added the **"Save Replay"** button (`#btn-save-replay`) in [`app/templates/index.html`](app/templates/index.html) and `saveAsReplay()` in [`app/static/js/workbench.js`](app/static/js/workbench.js), plus 2 new golden tests in [`golden_tests/test_replay.py`](golden_tests/test_replay.py).
