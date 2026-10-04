"""Golden acceptance test suite for Cosmic Conquest API contracts.

Verifies FastAPI endpoint availability, input validation, 400 rejection on non-adjacent moves,
and strict Sci-Fi movie trivia payload structure.
"""

from typing import Any

from fastapi.testclient import TestClient


def get_fastapi_app(workspace_path: Any) -> Any:
    """Dynamically import app from candidate workspace main.py."""
    import sys
    from importlib import import_module
    
    str_path = str(workspace_path)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)
    
    main_mod = import_module("main")
    return getattr(main_mod, "app")


def test_get_state_contract(candidate_workspace: Any) -> None:
    """Verify GET /api/game/state returns expected fields."""
    app = get_fastapi_app(candidate_workspace)
    client = TestClient(app)
    
    response = client.get("/api/game/state")
    assert response.status_code == 200
    data = response.json()
    
    assert "controlled_sectors" in data
    assert "shields" in data
    assert "energy" in data
    assert "status" in data
    assert "available_targets" in data
    assert "lv426" in data["available_targets"]


def test_attack_adjacent_sector_contract(candidate_workspace: Any) -> None:
    """Verify POST /api/game/attack with valid target returns Sci-Fi trivia challenge."""
    app = get_fastapi_app(candidate_workspace)
    client = TestClient(app)
    
    response = client.post("/api/game/attack", json={"target_sector": "lv426"})
    assert response.status_code == 200
    data = response.json()
    
    assert "question" in data
    assert "options" in data
    assert len(data["options"]) >= 2
    assert "movie_title" in data
    assert len(data["movie_title"]) > 0


def test_attack_non_adjacent_sector_rejected(candidate_workspace: Any) -> None:
    """Verify POST /api/game/attack rejects non-adjacent sectors with HTTP 400."""
    app = get_fastapi_app(candidate_workspace)
    client = TestClient(app)
    
    response = client.post("/api/game/attack", json={"target_sector": "arrakis"})
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data or "message" in data


def test_answer_combat_contract(candidate_workspace: Any) -> None:
    """Verify POST /api/game/answer resolves turn and updates game state."""
    app = get_fastapi_app(candidate_workspace)
    client = TestClient(app)
    
    # Request trivia challenge first
    attack_resp = client.post("/api/game/attack", json={"target_sector": "lv426"})
    assert attack_resp.status_code == 200
    
    # Submit answer
    answer_resp = client.post("/api/game/answer", json={"target_sector": "lv426", "chosen_index": 0})
    assert answer_resp.status_code == 200
    data = answer_resp.json()
    
    assert "correct" in data
    assert "explanation" in data
    assert "game_state" in data
