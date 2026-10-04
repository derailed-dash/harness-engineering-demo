"""Golden acceptance tests for the two-tier evaluation rubric.

Verifies:
- Check 1.8: Dynamic API Contract & Progression Topology (FastAPI boot & /api/game/state)
- Check 2.6: Progression Ergonomics & Interactivity
- 14-point scorecard coordination across mechanical and semantic tiers
"""

from pathlib import Path

from app.config import HARNESSED_DIR
from app.rubric.evaluator import evaluate_candidate_workspace
from app.rubric.mechanical import check_dynamic_api_contract, run_mechanical_tier
from app.rubric.semantic import _evaluate_heuristic_fallback


def test_check_1_8_dynamic_api_contract_harnessed() -> None:
    """Verify Check 1.8 validates FastAPI application startup and state progression."""
    result = check_dynamic_api_contract(HARNESSED_DIR)
    assert result["id"] == "1.8"
    assert result["passed"] is True
    assert result["score"] == 1.0
    assert "controlled territory" in result["details"]
    assert "active targets" in result["details"]


def test_check_1_8_dynamic_api_contract_missing_main(tmp_path: Path) -> None:
    """Verify Check 1.8 fails gracefully when main.py is missing."""
    result = check_dynamic_api_contract(tmp_path)
    assert result["id"] == "1.8"
    assert result["passed"] is False
    assert result["score"] == 0.0
    assert "main.py not found" in result["details"]


def test_check_1_8_dynamic_api_contract_broken_app(tmp_path: Path) -> None:
    """Verify Check 1.8 catches broken syntax or runtime import crashes."""
    bad_main = tmp_path / "main.py"
    bad_main.write_text("import non_existent_package_xyz\napp = None\n", encoding="utf-8")
    result = check_dynamic_api_contract(tmp_path)
    assert result["id"] == "1.8"
    assert result["passed"] is False
    assert result["score"] == 0.0
    assert "Dynamic API validation failed" in result["details"]


def test_mechanical_tier_check_count() -> None:
    """Verify mechanical tier executes exactly 8 checks."""
    checks = run_mechanical_tier(HARNESSED_DIR)
    assert len(checks) == 8
    check_ids = [c["id"] for c in checks]
    assert check_ids == ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8"]


def test_semantic_tier_heuristic_fallback_contains_2_6() -> None:
    """Verify semantic tier heuristic fallback evaluates 6 checks including 2.6."""
    checks = _evaluate_heuristic_fallback(HARNESSED_DIR)
    assert len(checks) == 6
    check_ids = [c["id"] for c in checks]
    assert check_ids == ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6"]

    c26 = checks[5]
    assert c26["id"] == "2.6"
    assert c26["name"] == "Progression Ergonomics & Interactivity"
    assert c26["passed"] is True
    assert c26["score"] == 1.0


def test_full_rubric_coordination() -> None:
    """Verify evaluate_candidate_workspace evaluates all 14 criteria with max_score 14.0."""
    scorecard = evaluate_candidate_workspace(HARNESSED_DIR)
    assert scorecard["max_score"] == 14.0
    assert len(scorecard["tier_1_mechanical"]) == 8
    assert len(scorecard["tier_2_semantic"]) == 6
    assert scorecard["score"] >= 13.0
