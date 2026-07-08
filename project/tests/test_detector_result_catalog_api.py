from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from detector_result_test_utils import override_detector_service


def test_detector_catalog_api_returns_capability_statuses_without_overstating_reserved_detectors() -> (
    None
):
    with override_detector_service():
        response = TestClient(app).get("/api/v1/detectors/catalog")

    assert response.status_code == 200
    payload = response.json()
    items = payload["items"]
    by_id = {item["detector_id"]: item for item in items}

    assert by_id["purchase_interval_ipi"]["status"] == "implemented"
    assert by_id["purchase_quantity_trend"]["status"] == "implemented"
    assert by_id["purchase_frequency_drop"]["status"] == "implemented"
    assert by_id["sku_shrink"]["status"] == "interface_only"
    assert by_id["fulfillment_gap"]["status"] == "experimental"
    assert by_id["price_competition"]["status"] == "reserved"
    assert by_id["peer_contrast"]["status"] == "reserved"
    assert by_id["price_competition"]["enabled_by_default"] is False
    assert by_id["peer_contrast"]["enabled_by_default"] is False
    assert payload["semantic_caveats"]
    assert "detector_probability" not in json.dumps(payload)
