from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.main import app


def test_legacy_and_feature_unit_debug_return_same_product_line_unit() -> None:
    client = TestClient(app)
    query = {"dataset_name": "sample", "as_of_date": "2025-12-31"}
    legacy = client.get("/api/v0/debug/unit/ORG_A/PL_A", params=query)
    feature = client.get("/api/v0/debug/unit/ORG_A/product_line/PL_A", params=query)

    assert legacy.status_code == 200
    assert feature.status_code == 200
    legacy_payload = legacy.json()
    feature_payload = feature.json()
    assert legacy_payload["feature_snapshot"]["unit_id"] == "ORG_A|product_line|PL_A"
    assert feature_payload["feature_snapshot"]["unit_id"] == "ORG_A|product_line|PL_A"
    assert legacy_payload["feature_snapshot"] == feature_payload["feature_snapshot"]


def test_legacy_and_feature_unit_debug_share_detector_outputs() -> None:
    client = TestClient(app)
    query = {"dataset_name": "sample", "as_of_date": "2025-12-31"}
    legacy = client.get("/api/v0/debug/unit/ORG_C/PL_A", params=query).json()
    feature = client.get("/api/v0/debug/unit/ORG_C/product_line/PL_A", params=query).json()

    assert legacy["detector_results"] == feature["detector_results"]
    assert {
        detector["evidence_refs"][0]["ref_type"]
        for detector in legacy["detector_results"]
        if detector["evidence_refs"]
    } == {"feature_snapshot"}


def test_dry_run_still_returns_feature_detector_statistics() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v0/inspection/dry-run",
        json={"dataset_name": "sample", "as_of_date": date(2025, 12, 31).isoformat()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["clue_count"] >= 1
    assert payload["feature_count"] > 0
    assert payload["detector_hit_distribution"]
