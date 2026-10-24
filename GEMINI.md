# Cosmic Conquest: Harness Engineering Demo Guidelines

## Mandatory Reading

- Read my associated blog article: https://dev.to/gde/loop-engineering-in-the-harness-autonomous-self-correcting-systems-part-2-155e
- README.md
- TODO.md

## Core Principles & Vocabulary Standards

### 1. Track Terminology Standards

- **Track 1 is NEVER described as "one-shot"**:
  - We do NOT refer to Track 1 as "one-shot" or "one-shot prompt".
  - Always call Track 1 **"Unharnessed (Single Pass)"** or **"Unharnessed (Vibe Coding)"**.
  - Track 1 ([`app/agents/unharnessed.py`](app/agents/unharnessed.py)) represents prompting the raw LLM directly with the specification in a single pass via a bare Google ADK `Agent(instruction="", tools=[])` without engineering guardrails, active skills, unit tests, or iterative self-healing loops.
- **Track 2 is "Harnessed Loop"**:
  - Track 2 ([`app/agents/agent.py`](app/agents/agent.py), [`app/agents/harnessed.py`](app/agents/harnessed.py) & [`app/agents/tools.py`](app/agents/tools.py)) represents Harness Engineering implemented via a Google ADK `LoopAgent`: specialised skills, test-driven development (TDD), living memory persistence, linting feedback, and autonomous multi-turn self-healing gated by `RubricEvaluationGateAgent(BaseAgent)`.

### 2. Specification & Context Architecture

- **Single Canonical Specification**:
  - The shared specification lives exclusively in `specs/cosmic_conquest_spec.md`.
  - Both Track 1 (Unharnessed) and Track 2 (Harnessed) receive and consume this exact same specification file.
  - Required output deliverables are declared directly in Section 3.4 of `specs/cosmic_conquest_spec.md`.
  - **No extra context in code**: Neither `unharnessed.py` nor `harnessed.py` may inject hidden application context, instructions, or requirements not present in the external files.
- **Persona, Harness Instructions & Rubric**:
  - Persona instructions, role definitions, and engineering guardrails belong exclusively in `harness/harness_context.md`.
  - Semantic evaluation rubric criteria (2.1–2.6) live declaratively in `harness/RUBRIC.md`.
  - Track 1 (Unharnessed) receives NO persona and NO additional harness context.

### 3. Living Memory Ledger

- Harness memory and evaluation history are recorded dynamically in `harness/output/LIVING_MEMORY.md`.
- In a fresh comparison run, the previous living memory is wiped clean before starting.
- Living memory is rendered live in the Workbench UI feed and can be inspected in the markdown output directory.

### 4. Model, Thinking & Output Token Configuration (`gemini-3.8-flash`)

- **Default Output Token Limit (`65,536`)**:
  - Do NOT artificially cap `max_output_tokens` to a small value (e.g. `4096`) on single-pass or multi-file generation turns. In `gemini-3.8-flash`, thinking tokens and visible output tokens share `max_output_tokens`, and a single pass generating a multi-file application can legitimately emit large output; setting `max_output_tokens` too low prematurely truncates/prunes the model's output.
  - Default `MAX_OUTPUT_TOKENS` in [`app/config.py`](app/config.py) is `65536` (matching the `google-genai` SDK's 64K default for `gemini-3.8-flash`).
- **Thinking Level (`ThinkingLevel.LOW`)**:
  - `thinking_budget` is deprecated on Gemini 3.x+ models, and `ThinkingLevel.MINIMAL` is not supported on `gemini-3.8-flash` (returns a `400` error). Use `ThinkingLevel.LOW` (`types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)`) to minimise latency and cost while preserving reasoning quality.
- **WSL2 IPv4 Binding & `X-Server-Timeout`**:
  - In WSL2, bind `httpx` sync/async transports to `local_address="0.0.0.0"` with `retry_options=types.HttpRetryOptions(attempts=1)` in [`app/client_factory.py`](app/client_factory.py) to avoid IPv6 blackhole stalls and 5x `tenacity` retry loops.
  - Remember that `google-genai` populates the `X-Server-Timeout` HTTP header from `HttpOptions.timeout`; ensure `timeout` on `unharnessed_vibe_agent` and `_build_ipv4_http_options` (`240_000` ms / 4 minutes) is generous enough for a >2-minute single-pass generation so Vertex AI does not abort it mid-generation with `504 DEADLINE_EXCEEDED`.

### 5. Code Standards & UK English

- Use English UK spelling throughout (`behaviour`, `initialised`, `synchronise`, `colour`, `specialised`).
- NEVER use `file:///` URI paths in markdown documentation, responses, or link references; use relative markdown paths.
- Ensure all Python code satisfies `codespell` and `ruff check --fix .`.
