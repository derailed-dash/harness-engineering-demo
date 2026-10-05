---
name: test-driven-development
description: Drives development with tests using the red-green-refactor loop. Use when implementing any logic, fixing any bug, or changing any behaviour.
---

# Test-Driven Development (TDD) Skill

## Overview

Write a failing test before writing the code that makes it pass. Tests are proof — "seems right" is not done. A codebase with good tests is an AI agent's superpower; a codebase without tests is a liability.

## When to Use

- Implementing any new logic, game mechanics, state machines, or domain rules
- Fixing any bug or edge case (reproduce the issue with a failing test first)
- Refactoring internal code structure whilst preserving functional behaviour

## The TDD Cycle

```text
    RED                GREEN              REFACTOR
 Write a test    Write minimal code    Clean up the
 that fails  ──→  to make it pass  ──→  implementation  ──→  (repeat)
      │                  │                    │
      ▼                  ▼                    ▼
   Test FAILS        Test PASSES         Tests still PASS
```

### 1. RED — Write Failing Unit Tests First
- Locate or create the unit test suite under `tests/` (e.g. `tests/test_game.py`).
- Author unit test assertions that define the expected behaviour, inputs, outputs, and edge cases.
- Execute `pytest tests/` and verify that the tests fail for the expected reason (e.g. missing function or unhandled state).

### 2. GREEN — Implement Minimal Code
- Write the minimal application logic required to satisfy the unit test assertions.
- Re-run `pytest tests/` and ensure all tests pass cleanly.

### 3. REFACTOR — Clean Up and Harden
- Eliminate code duplication, improve naming, add docstrings, and run static analysis (`ruff check`).
- Ensure all tests remain passing after refactoring.
