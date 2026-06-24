from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_database_smoke_test_without_database_url_returns_clear_error(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "")

    response = TestClient(app).post(
        "/api/v0/smoke-test/database",
        json={
            "as_of_date": "2026-06-24",
            "days": 14,
            "row_limit": 100,
            "include_debug_features": False,
        },
    )

    assert response.status_code == 400
    assert "DATABASE_URL is not configured" in response.json()["detail"]


def test_database_freshness_without_database_url_returns_clear_error(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "")

    response = TestClient(app).post(
        "/api/v0/smoke-test/freshness",
        json={"as_of_date": "2026-06-24", "days": 14},
    )

    assert response.status_code == 400
    assert "DATABASE_URL is not configured" in response.json()["detail"]
