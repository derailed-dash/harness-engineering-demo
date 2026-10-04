# Unharnessed Candidate Workspace

This directory is the runtime output target for the **Unharnessed Approach (Vibe Coding)**.

## How It Works
When a comparison is triggered via the Workbench:
1. The model is sent the raw goal prompt with no `GEMINI.md` context, no specialised skills, and no loop.
2. The resulting single-turn files (`game_engine.py`, `trivia_service.py`, `main.py`) are extracted into this folder on-demand.
3. The evaluation engine runs the two-tier rubric against this directory at the end of the run.
4. The live prototype is mounted and served at `/preview/unharnessed` for interactive inspection.

> **Note**: Generated source files are created dynamically at runtime and excluded from git tracking.
