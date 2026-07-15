from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from frontend_api_test_utils import override_frontend_result_repository


def test_daily_detector_clues_use_result_batch_display_lookup() -> None:
    with override_frontend_result_repository():
        response = TestClient(app).get(
            "/api/v1/daily-detector/clues",
            params={"sort_by": "detector_score"},
        )

    assert response.status_code == 200
    payload = response.json()
    rule_only = next(item for item in payload["clues"] if item["clue_id"] == "clue_rule_only")
    assert rule_only["manufacturer_display_name"] == "Manufacturer One"
    assert rule_only["manufacturer_name"] == "Manufacturer One"
    assert rule_only["hospital_name"] == "Rule Only Hospital"
    assert rule_only["drug_name"] == "Rule Only Drug"
    assert rule_only["hospital_name"] != rule_only["hospital_code"]
    assert rule_only["drug_name"] != rule_only["drug_group"]
