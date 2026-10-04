"""Two-tier evaluation rubric coordinator.

Combines Tier 1 (Mechanical) and Tier 2 (Semantic) checks to produce a comprehensive
scorecard with pass/fail gates and diagnostics for living memory feedback.
"""

from pathlib import Path
from typing import Any

from app.rubric.mechanical import run_mechanical_tier
from app.rubric.semantic import run_semantic_tier
from app.token_tracker import TokenMetrics


def evaluate_candidate_workspace(
    workspace_path: Path,
    trajectory: list[dict[str, Any]] | None = None,
    token_tracker: TokenMetrics | None = None,
) -> dict[str, Any]:
    """Run full rubric on candidate workspace.
    
    Returns structured scorecard, total score, passing status, and actionable
    diagnostic feedback for the next loop iteration.
    """
    mechanical_checks = run_mechanical_tier(workspace_path, trajectory)
    semantic_checks = run_semantic_tier(workspace_path, token_tracker)
    
    all_checks = mechanical_checks + semantic_checks
    total_score = sum(c["score"] for c in all_checks)
    max_score = float(len(all_checks))
    is_passing = total_score >= max_score
    
    failed_checks = [c for c in all_checks if not c["passed"]]
    diagnostic_feedback = [f"- Check {c['id']} ({c['name']}) FAILED: {c['details']}" for c in failed_checks]

    return {
        "score": total_score,
        "max_score": max_score,
        "is_passing": is_passing,
        "tier_1_mechanical": mechanical_checks,
        "tier_2_semantic": semantic_checks,
        "failed_checks": failed_checks,
        "diagnostics": "\n".join(diagnostic_feedback) if diagnostic_feedback else f"All {len(all_checks)} rubric checks satisfied 100%.",
    }
