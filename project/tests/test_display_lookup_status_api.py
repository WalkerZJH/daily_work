from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from frontend_api_test_utils import override_frontend_result_repository


def test_display_lookup_status_returns_readiness_fields_without_404() -> None:
    with override_frontend_result_repository():
        response = TestClient(app).get("/api/v1/display-lookup/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] == "conditional"
    assert payload["hospital_name_ready"] is True
    assert payload["drug_name_ready"] is True
    assert payload["manufacturer_name_ready"] is True
    assert payload["region_ready"] is True
    assert payload["fallback_policy"] == "batch_display_name_or_code_fallback"
