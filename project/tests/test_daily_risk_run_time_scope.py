from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_detector_run_returns_daily_time_scope() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v0/detectors/run",
        json={
            "source_type": "csv",
            "dataset_name": "sample",
            "as_of_date": "2025-12-31",
            "lookback_days": 30,
            "baseline_days": 180,
            "enabled_detectors": ["low_delivery_rate_warning"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    for field in ["as_of_date", "lookback_start_date", "baseline_start_date", "baseline_end_date"]:
        assert field in payload["summary"]
        assert field in payload["detector_results"][0]
    assert payload["detector_results"][0]["run_scope"]["source_type"] == "csv"
