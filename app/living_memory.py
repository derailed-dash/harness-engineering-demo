"""Living Memory & Diagnostic Ledger Manager.

Maintains an autonomous loop memory ledger persisted to disk at harness/output/LIVING_MEMORY.md.
Records iterations, rubric evaluations, actionable failure diagnostics, and remediation hypotheses.
Enables crash resilience, loop restart, and real-time UI inspection.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import HARNESS_OUTPUT_DIR, LIVING_MEMORY_PATH


class LivingMemoryManager:
    """Manages reading, appending, and resetting the markdown living memory ledger."""

    def __init__(self, output_path: Path | None = None) -> None:
        self.output_path = output_path or LIVING_MEMORY_PATH
        self.output_dir = self.output_path.parent or HARNESS_OUTPUT_DIR

    def reset(self) -> None:
        """Pristine reset for fresh comparison runs: delete or re-initialise ledger."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.output_path.exists():
            self.output_path.unlink()

    def get_content(self) -> str:
        """Retrieve current living memory ledger markdown, or default placeholder."""
        if self.output_path.is_file():
            return self.output_path.read_text(encoding="utf-8")
        return (
            "# Living Memory & Diagnostic Ledger\n\n"
            "*Status: No active run. Waiting for comparison or presentation replay.*"
        )

    def init_ledger(self, session_id: str, goal_spec: str) -> str:
        """Create initial ledger header at the start of a fresh autonomous harness run."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        header = (
            "# Living Memory & Diagnostic Ledger\n\n"
            "## Session Context\n"
            f"- **Session ID**: `{session_id}`\n"
            f"- **Initialised**: {timestamp}\n"
            f"- **Goal**: `{goal_spec}`\n"
            "- **Loop Controller**: ADK Autonomous Engine with Turn-by-Turn Rubric Gate\n\n"
            "---\n\n"
        )
        self.output_path.write_text(header, encoding="utf-8")
        return header

    def record_iteration(
        self,
        iteration: int,
        max_iterations: int,
        scorecard: dict[str, Any],
        actions_taken: list[str] | None = None,
        strategy_notes: str | None = None,
    ) -> str:
        """Record the evaluation scorecard, failure diagnostics, and remediation strategy."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        score = scorecard.get("score", 0.0)
        max_score = scorecard.get("max_score", 14.0)
        is_passing = scorecard.get("is_passing", False)
        status_label = "PASSED (Gate Satisfied)" if is_passing else "FAILED (Self-Healing Required)"

        lines: list[str] = [
            f"## Iteration {iteration} / {max_iterations} [{timestamp}]\n",
            f"- **Score**: `{score:.1f} / {max_score:.1f}` ({status_label})\n",
        ]

        if actions_taken:
            lines.append("- **Files Authored / Modified**:\n")
            for action in actions_taken:
                lines.append(f"  - `{action}`\n")

        failed_checks = scorecard.get("failed_checks", [])
        if failed_checks:
            lines.append("\n### Active Failures & Diagnostic Telemetry\n")
            for c in failed_checks:
                lines.append(f"1. **Check {c['id']} ({c['name']})**: {c.get('details', '')}\n")
        else:
            lines.append("\n### Rubric Status\n- All criteria passed cleanly. Zero defects detected.\n")

        if strategy_notes:
            lines.append(f"\n### Autonomous Remediation Strategy\n{strategy_notes}\n")

        lines.append("\n---\n\n")
        entry = "".join(lines)

        # Append to existing content or initialise if missing
        current = self.output_path.read_text(encoding="utf-8") if self.output_path.exists() else ""
        self.output_path.write_text(current + entry, encoding="utf-8")
        return entry
