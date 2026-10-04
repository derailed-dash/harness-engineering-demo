"""Verification test script for Harness Demo pipeline, evaluator, and golden tests."""

from app.agents.harnessed import _apply_harnessed_self_healing_iteration_2, _write_harnessed_iteration_1
from app.agents.unharnessed import _build_synthetic_unharnessed_app
from app.config import HARNESSED_DIR, UNHARNESSED_DIR
from app.rubric.evaluator import evaluate_candidate_workspace
from app.token_tracker import TokenMetrics


def run_pipeline_verification():
    print("--- 1. Testing Unharnessed Baseline Generation & Rubric ---")
    _build_synthetic_unharnessed_app(UNHARNESSED_DIR)
    unharnessed_tracker = TokenMetrics()
    unharnessed_eval = evaluate_candidate_workspace(UNHARNESSED_DIR, token_tracker=unharnessed_tracker)
    print(f"Unharnessed Score: {unharnessed_eval['score']:.1f} / {unharnessed_eval['max_score']:.1f} (Passing: {unharnessed_eval['is_passing']})")
    assert unharnessed_eval['score'] < unharnessed_eval['max_score'], "Unharnessed should not score 100%"

    print("\n--- 2. Testing Harnessed TDD & Self-Healing Pipeline ---")
    _write_harnessed_iteration_1(HARNESSED_DIR)
    _apply_harnessed_self_healing_iteration_2(HARNESSED_DIR)
    harnessed_tracker = TokenMetrics()
    harnessed_eval = evaluate_candidate_workspace(HARNESSED_DIR, token_tracker=harnessed_tracker)
    print(f"Harnessed Score: {harnessed_eval['score']:.1f} / {harnessed_eval['max_score']:.1f} (Passing: {harnessed_eval['is_passing']})")
    if harnessed_eval['failed_checks']:
        print("Harnessed Failed Checks:", harnessed_eval['failed_checks'])
    assert harnessed_eval['score'] == harnessed_eval['max_score'], (
        f"Harnessed solution should score {harnessed_eval['max_score']}/{harnessed_eval['max_score']}, got {harnessed_eval['score']}"
    )
    assert harnessed_eval['is_passing'] is True

    print("\n--- All Verification Checks Passed Successfully! ---")


if __name__ == "__main__":
    run_pipeline_verification()
