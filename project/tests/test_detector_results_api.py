from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from detector_result_test_utils import override_detector_service


def test_detector_results_api_exposes_traceable_evaluation_contract() -> None:
    with override_detector_service():
        response = TestClient(app).get(
            "/api/v1/detectors/results",
            params={"detector_id": "purchase_interval_ipi", "manufacturer_code": "m1"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["config_id"] == "cfg-1"
    assert len(item["config_hash"]) == 64
    assert item["eligibility_status"] == "applicable"
    assert item["comparison_value"] == 4.0
    assert item["threshold_operator"] == ">="
    assert "detector_probability" not in item
