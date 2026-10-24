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

### 2. Root-Cause Investigation & Fix for Track 2 Latency Stalls (`17d96e0`)
- [x] **Root Cause #1 — `thinking_budget=0` vs `thinking_level=ThinkingLevel.LOW` on `gemini-3.8-flash`**:
  - Per official Gemini 3.8 Flash documentation (`gemini-api-guides/generate-content/thinking.md` and `docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-3-8-flash`), `gemini-3.8-flash` replaces integer `thinking_budget` with `thinking_level` (`LOW`, `MEDIUM` (default), `HIGH`; `MINIMAL` is unsupported and returns HTTP 400).
  - Passing `thinking_budget=0` to `gemini-3.8-flash` did not disable thinking; the model still generated internal `thoughts_token_count` tokens on every call, turning each loop turn and semantic rubric check into a 30–75s+ reasoning pass.
  - **Fix**: Switched `create_builder_agent` ([`app/agents/agent.py`](app/agents/agent.py)) and `run_semantic_tier` ([`app/rubric/semantic.py`](app/rubric/semantic.py)) to `types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)` (with `max_output_tokens=2048` on the ~500-token JSON rubric judge).
  - **Constraint Preserved**: Track 1 ([`app/agents/unharnessed.py`](app/agents/unharnessed.py)) is completely untouched (`MAX_OUTPUT_TOKENS = 32768`, full default thinking).
- [x] **Root Cause #2 — Unrouted IPv6 (`AF_INET6`) Socket Stalls with `timeout=None` in `google-genai`**:
  - On Linux/WSL2 hosts where `aiplatform.googleapis.com` resolves to both IPv4 and unrouted IPv6 (`2a00:1450:4009:...`) addresses, `google-genai`'s default `httpx.Client(timeout=None)` / `httpx.AsyncClient(timeout=None)` occasionally hit an IPv6 address first and hung in the kernel TCP SYN retransmission loop for 130–220s before falling back to IPv4.
  - **Fix**: Added `_build_ipv4_http_options()` in [`app/client_factory.py`](app/client_factory.py) binding both sync and async `httpx` transports to `local_address="0.0.0.0"`, reducing TCP+TLS connect time to ~16–25ms.
- [x] **Root Cause #3 — Import-Time Client Instantiation & Repeated Cold ADC Lookups**:
  - Updated `_create_default_root_agent()` in [`app/agents/agent.py`](app/agents/agent.py) to pass `model=DEFAULT_MODEL` (`"gemini-3.8-flash"`) rather than instantiating a network client at module import time.
  - Added `_get_cached_adc()` in [`app/client_factory.py`](app/client_factory.py) so ADC credentials and refreshed OAuth bearer tokens are reused across turns.

---

## Next Session (To Investigate on Other Machine)

- [ ] **Investigate Why Track 1 (Unharnessed Single Pass) Scored `12.0 / 14.0` on Latest Run**:
  - Historically, Track 1 (Unharnessed / Vibe Coding) scores significantly lower (e.g. `6.0–8.0 / 14.0`).
  - In the latest manual run recorded in [`app/replay/replay_data.json`](app/replay/replay_data.json) and [`snapshots/unharnessed/`](snapshots/unharnessed/) (`17d96e0`), Track 1 scored `12.0 / 14.0`.
  - **Questions to investigate next**:
    1. Which 12 checks passed and which 2 failed on Track 1 in that run (Tier 1 Mechanical `1.1–1.8` vs Tier 2 Semantic `2.1–2.6`)?
    2. Did switching `run_semantic_tier` to `ThinkingLevel.LOW` make the LLM-as-a-Judge (`gemini-3.8-flash`) overly lenient on Tier 2 semantic checks (`2.1–2.6`) for Track 1, or did `gemini-3.8-flash` genuinely one-pass more of the spec (`specs/cosmic_conquest_spec.md`), or did `_extract_and_write_files` / fallback baseline behaviour play a role?
    3. Compare the recorded Track 1 scorecard and generated files in [`snapshots/unharnessed/`](snapshots/unharnessed/) and [`app/replay/replay_data.json`](app/replay/replay_data.json) against previous commits (`git diff 2818a2b 17d96e0 -- app/replay/replay_data.json snapshots/unharnessed/`).

