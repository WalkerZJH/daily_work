from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app


def test_formal_mode_without_result_batch_dir_does_not_return_demo_payload(monkeypatch) -> None:
    from app.api.routes_frontend_pages import get_frontend_page_service

    monkeypatch.delenv("RISK_RESULT_BATCH_ROOT", raising=False)
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
    assert payload["data_source"] == "unavailable"
    assert payload["demo_mode"] is False
    text = json.dumps(payload, ensure_ascii=False).lower()
    assert "mock" not in text


def test_mock_mode_is_explicit_when_allowed(monkeypatch) -> None:
    from app.api.routes_frontend_pages import get_frontend_page_service

    monkeypatch.delenv("RISK_RESULT_BATCH_ROOT", raising=False)
    monkeypatch.delenv("RISK_RESULT_BATCH_DIR", raising=False)
    monkeypatch.setenv("ALLOW_MOCK_PAYLOADS", "true")
    get_frontend_page_service.cache_clear()
    try:
        response = TestClient(app).get("/api/v1/workbench")
    finally:
        get_frontend_page_service.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["demo_mode"] is True
    assert payload["data_source"] == "mock"
    assert payload["ready"] is False
