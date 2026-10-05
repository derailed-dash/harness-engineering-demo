# Cosmic Conquest: Harness Engineering Demo Guidelines

## Core Principles & Vocabulary Standards

### 1. Track Terminology Standards
- **Track 1 is NEVER "one-shot"**:
  - We do NOT refer to Track 1 as "one-shot" or "one-shot prompt".
  - Always call Track 1 **"Unharnessed (Single Pass)"** or **"Unharnessed (Vibe Coding)"**.
  - Track 1 represents prompting the raw LLM directly with the specification in a single pass without engineering guardrails, active skills, unit tests, or iterative self-healing loops.
- **Track 2 is "Harnessed Loop"**:
  - Track 2 represents Harness Engineering: specialized skills, test-driven development (TDD), living memory persistence, linting feedback, and autonomous multi-turn self-healing.

### 2. Specification & Context Architecture
- **Single Canonical Specification**:
  - The shared specification lives exclusively in `specs/cosmic_conquest_spec.md`.
  - Both Track 1 (Unharnessed) and Track 2 (Harnessed) receive and consume this exact same specification file.
  - Required output deliverables are declared directly in Section 3.4 of `specs/cosmic_conquest_spec.md`.
  - **No extra context in code**: Neither `unharnessed.py` nor `harnessed.py` may inject hidden application context, instructions, or requirements not present in the external files.
- **Persona & Harness Instructions**:
  - Persona instructions, role definitions, and engineering guardrails belong exclusively in `harness/harness_context.md`.
  - Track 1 (Unharnessed) receives NO persona and NO additional harness context.

### 3. Living Memory Ledger
- Harness memory and evaluation history are recorded dynamically in `harness/output/LIVING_MEMORY.md`.
- In a fresh comparison run, the previous living memory is wiped clean before starting.
- Living memory is rendered live in the Workbench UI feed and can be inspected in the markdown output directory.

### 4. Code Standards & UK English
- Use English UK spelling throughout (`behaviour`, `initialised`, `synchronise`, `colour`).
- NEVER use `file:///` URI paths in markdown documentation, responses, or link references; use relative markdown paths.
- Ensure all Python code satisfies `codespell` and `ruff check --fix .`.
