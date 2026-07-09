from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app


def test_formal_mode_without_result_batch_dir_does_not_inject_default_payload_or_metrics(monkeypatch) -> None:
    from app.api.routes_frontend_pages import get_frontend_page_service

    monkeypatch.delenv("RISK_RESULT_BATCH_DIR", raising=False)
    monkeypatch.delenv("ALLOW_MOCK_PAYLOADS", raising=False)
    get_frontend_page_service.cache_clear()
    try:
        response = TestClient(app).get("/api/v1/workbench")
    finally:
        get_frontend_page_service.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["rows"] == []
    assert payload["monthly_risk_entities"] == []
    text = json.dumps(payload, ensure_ascii=False)
    assert "model_metrics" not in text
    assert "DEFAULT_MODEL_METRICS" not in text
    assert "proof_case" not in text.lower()


def test_formal_mode_without_result_batch_dir_does_not_claim_batch_manufacturer_ready(monkeypatch) -> None:
    monkeypatch.delenv("RISK_RESULT_BATCH_DIR", raising=False)
    monkeypatch.delenv("ALLOW_MOCK_PAYLOADS", raising=False)

    response = TestClient(app).get("/api/v1/my/manufacturers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["scope_source"] == "result_batch_unavailable"
    assert payload["manufacturers"] == []
    assert payload["date_resolution_status"] == "no_available_batch"
