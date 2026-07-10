from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from detector_result_test_utils import override_detector_service


def test_risk_entity_detector_evidence_api_attaches_evidence_only_to_existing_risk_entity() -> None:
    with override_detector_service():
        response = TestClient(app).get("/api/v1/risk-entities/entity_high/detector-evidence")

    assert response.status_code == 200
    payload = response.json()

    assert payload["risk_entity_id"] == "entity_high"
    assert payload["monthly_risk_probability"] == 0.91
    assert payload["monthly_loss_value"] == 910
    assert payload["items"][0]["detector_id"] == "purchase_interval_ipi"
    assert payload["items"][0]["detector_score"] == 0.82
    assert payload["items"][0]["detector_family_label"] == "采购间隔"
    assert payload["items"][0]["detector_name_label"] == "Purchase Interval Ipi"
    assert payload["catalog_by_detector_id"]["purchase_interval_ipi"]["status"] == "implemented"
    assert "detector_probability" not in json.dumps(payload)


def test_risk_entity_detector_evidence_api_returns_404_for_unknown_risk_entity() -> None:
    with override_detector_service():
        response = TestClient(app).get("/api/v1/risk-entities/not_a_risk_entity/detector-evidence")

    assert response.status_code == 404
