from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_options_api_returns_code_and_name(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    client = TestClient(app)

    enterprises = client.get("/api/v0/options/enterprises")
    provinces = client.get("/api/v0/options/provinces")
    product_lines = client.get("/api/v0/options/product-lines")
    categories = client.get("/api/v0/options/detector-categories")
    detectors = client.get("/api/v0/options/detectors?category=delivery_response")

    for response in [enterprises, provinces, product_lines, categories, detectors]:
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    assert {"code", "name"}.issubset(product_lines.json()[0])
    assert {"category_id", "category_name", "detector_count"}.issubset(categories.json()[0])
    assert all(item["detector_id"].endswith("_warning") for item in detectors.json())
