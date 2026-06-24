from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_dry_run_risk_card_contains_backbone_prediction() -> None:
    response = TestClient(app).post(
        "/api/v0/inspection/dry-run",
        json={"dataset_name": "sample", "as_of_date": "2025-12-31"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_card_candidates"]
    card = payload["risk_card_candidates"][0]
    assert "backbone" in card
    assert card["backbone"]["backbone_model"] in {
        "palive_lgbm",
        "palive_interval_proxy",
        "palive_bgnbd",
        "not_available",
        "heuristic",
    }
    assert "warnings" in card["backbone"]
