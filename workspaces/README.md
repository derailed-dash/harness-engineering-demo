# Dynamic Workspaces Directory (Layer 2)

This directory hosts the isolated ephemeral workspaces where coding agents generate candidate solutions on-demand during Workbench execution.

## Structure
* [`unharnessed/`](unharnessed/): Output destination for the single-turn open-loop (Vibe Coding) run.
* [`harnessed/`](harnessed/): Output destination for the iterative ADK Loop Engineering run.

> **Note**: All generated code files (`*.py`, `static/`, `tests/`) are generated on-demand and intentionally excluded from git tracking. The directories themselves are preserved via these README files.
