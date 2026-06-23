from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_dry_run_api_returns_level_distribution() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v0/inspection/dry-run",
        json={"dataset_name": "sample", "as_of_date": "2025-12-31"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["clue_count"] >= 3
    assert {"red", "orange", "yellow"}.issubset(payload["risk_level_distribution"])
    assert payload["detector_hit_distribution"]["inactive_terminal"] >= 1
    assert payload["detector_hit_distribution"]["new_terminal"] >= 1
    assert payload["detector_hit_distribution"]["sku_shrink"] >= 1
    assert payload["enabled_preprocessors"]
    assert payload["feature_count"] > 0
    assert "detector_skipped_due_to_missing_features" in payload
    assert "warning_summary" in payload
