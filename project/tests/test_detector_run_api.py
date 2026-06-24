from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_detector_run_sample_mode_returns_summary_and_results() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v0/detectors/run",
        json={
            "source_type": "csv",
            "dataset_name": "sample",
            "as_of_date": "2025-12-31",
            "enabled_detectors": ["low_delivery_rate_warning"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert {"summary", "detector_results", "warning_summary"}.issubset(payload)
    assert payload["summary"]["detector_count"] == 1
    assert all(item["detector_id"] == "low_delivery_rate_warning" for item in payload["detector_results"])


def test_detector_run_interface_only_detector_does_not_crash() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v0/detectors/run",
        json={
            "source_type": "csv",
            "dataset_name": "sample",
            "as_of_date": "2025-12-31",
            "enabled_detectors": ["substitution_risk"],
        },
    )

    assert response.status_code == 200
    result = response.json()["detector_results"][0]
    assert result["hit"] is False
    assert result["status"] in {"reserved", "interface_only"}

