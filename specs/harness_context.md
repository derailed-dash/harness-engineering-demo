# Engineering Context & Harness Guardrails (GEMINI.md)

This engineering context acts as the persistent workspace instructions (`GEMINI.md`) supplied exclusively to the **Harnessed Pipeline**. The unharnessed "vibe coding" track does not receive these guardrails and relies solely on the raw goal specification.

---

## 1. Environment & Coding Standards
- **Python Version**: Python 3.13 standard.
- **Type Hinting**: Strict PEP 585 (use built-in `list[str]`, `dict[str, Any]`, `tuple[int, ...]`, never use deprecated `typing.List` or `typing.Dict`).
- **Scope Discipline**: Only create required files (`game_engine.py`, `trivia_service.py`, `main.py`, `tests/test_game.py`, `static/index.html`). Do not generate speculative helper files, hallucinated third-party dependencies, or dead code.

---

## 2. Test-Driven Development (TDD)
- **Mandatory Test Suite**: Author a comprehensive unit test suite in `tests/test_game.py` covering star map adjacency graph traversal, combat resolution, and victory/defeat rules before or alongside implementation.
- **Verification Gate**: Verify that all unit tests pass cleanly via `pytest` before declaring any task complete.

---

## 3. Backend Architecture & Security Guardrails
- **Parameterisation**: All API request bodies and input parameters must use structured Pydantic models with input validation. Never accept raw unvalidated dictionaries or execute dynamic evaluation (`eval`, `exec`).
- **Error Handling**: Non-adjacent sector attacks or invalid moves must trigger actionable HTTP 400 responses without leaking internal stack traces.
- **Sci-Fi Movie Trivia Grounding**: Every trivia question must reference a real, canonical Sci-Fi movie (e.g. *Blade Runner*, *Alien*, *The Matrix*, *Dune*, *2001: A Space Odyssey*, *Solaris*). Never use generic space lore.
- **Architectural Integrity**: Maintain strict modular boundaries. Game engine pure mechanics; Trivia service separate; FastAPI endpoints for HTTP routing; Static UI.
- **Documentation**: Include clear top-of-module docstrings explaining architectural intent and design rationale.

---

## 4. Frontend Client Contract (`static/index.html`)
- Deliver a complete, self-contained interactive client implementing Section 3.3 of the specification:
  1. Star Map sector visualisation with dynamic status styling (controlled, valid target, locked).
  2. Real-time HUD displaying shields, energy, liberated sectors, and fleet status.
  3. Interactive combat challenge modal dialogue triggered by sector clicks.
  4. Active client-side fetch calls to `/api/game/attack`, `/api/game/answer`, and `/api/game/state` to update HUD and territory in real time.
