from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_frontend_workbench_returns_customer_rows_without_legacy_fields_or_model_metrics() -> None:
    response = TestClient(app).get(
        "/api/v1/workbench",
        params={"horizon": "H6", "top_n": 5, "sort_by": "risk_probability"},
    )

    assert response.status_code == 200
    payload = response.json()
    rows = payload["rows"]

    assert payload["batch_context"]["primary_horizon"] == "H6"
    assert len(rows) <= 5
    assert all({"manufacturer_code", "hospital_name", "drug_name"}.issubset(row) for row in rows)
    assert all("loss_value" in row for row in rows)
    text = response.text
    for forbidden in ["business_score", "fill_policy", "expected_loss", "model_metrics"]:
        assert forbidden not in text


def test_frontend_risk_entities_and_detail_expose_horizons_detectors_and_explanations() -> None:
    client = TestClient(app)

    list_response = client.get("/api/v1/risk-entities")
    assert list_response.status_code == 200
    entities = list_response.json()["entities"]
    assert entities
    assert "business_score" not in list_response.text

    detail_response = client.get(f"/api/v1/risk-entities/{entities[0]['entity_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()

    assert detail["entity"]["entity_id"] == entities[0]["entity_id"]
    assert set(detail["horizon_profiles"]) == {"H3", "H6", "H12"}
    assert "selected_horizon_profile" in detail
    for profile in detail["horizon_profiles"].values():
      assert profile["detector_results"]
      assert "xgboost_shap" in profile
      assert profile["detector_narrative"]


def test_frontend_oneshot_never_exposes_prediction_fields() -> None:
    response = TestClient(app).get("/api/v1/oneshot-terminals")

    assert response.status_code == 200
    payload = response.json()

    assert payload["summary"]["oneshot_count"] == payload["total"]
    forbidden = {"repurchase_propensity", "expected_repurchase_amount", "priority", "ranking_basis"}
    assert all(forbidden.isdisjoint(item) for item in payload["items"])
    if payload["ready"] is False:
        assert payload["error_code"] == "ONESHOT_RESULT_NOT_AVAILABLE"
        assert payload["items"] == []


def test_removed_watchlist_page_api_is_not_exposed() -> None:
    response = TestClient(app).get("/api/v1/watchlist")

    assert response.status_code == 404
