# Harnessed Candidate Workspace

This directory is the runtime output target for the **Harnessed Approach (Autonomous ADK Loop Engineering)**.

## How It Works
When a comparison is triggered via the Workbench:
1. The ADK agent is provided with the explicit Goal alongside `GEMINI.md` context (Python 3.13, strict PEP 585 typing, and mandatory TDD).
2. The agent authors unit tests first in `tests/test_game.py` and implements the application.
3. Every iteration is gated against the 10-point rubric from Part 2 of the blog series.
4. Failure diagnostics feed into living memory, guiding autonomous self-healing until 10/10 criteria are satisfied.
5. The verified game is mounted and served at `/preview/harnessed` for live play in the Arcade Preview.

> **Note**: Generated source files and test suites are created dynamically at runtime and excluded from git tracking.
