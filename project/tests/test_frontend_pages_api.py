from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_frontend_workbench_returns_twenty_rows_sorted_by_business_score() -> None:
    response = TestClient(app).get("/api/v1/workbench")

    assert response.status_code == 200
    payload = response.json()
    rows = payload["rows"]

    assert payload["batch_context"]["primary_horizon"] == "H6"
    assert payload["fill_policy"]["workbench_target_count"] == 20
    assert len(rows) == 20
    assert all({"manufacturer_code", "hospital_name", "drug_name"}.issubset(row) for row in rows)

    scores = [row["business_score"] for row in rows]
    assert scores == sorted(scores, reverse=True)
    assert all(row["business_score"] == round(row["risk_probability"] * row["average_consumption_in_window"]) for row in rows)


def test_frontend_workbench_exposes_model_metrics_with_actual_topk_share() -> None:
    response = TestClient(app).get("/api/v1/workbench")

    assert response.status_code == 200
    metrics = response.json()["model_metrics"]

    assert metrics
    for metric in metrics:
        assert {"auc", "prauc", "ece", "brier", "topk_recall"}.issubset(metric)
        for topk in metric["topk_recall"]:
            actual_share = round(topk["selected_count"] / topk["evaluation_population"], 4)
            assert topk["actual_k_percent"] == actual_share
            assert 0 <= topk["recall"] <= 1

    union_metric = next(item for item in metrics if item["model_id"] == "detector_evidence_ranker")
    union_topk = union_metric["topk_recall"][0]
    assert union_topk["k_policy"] == "union_backfilled_actual_share"
    assert union_topk["actual_k_percent"] > union_topk["requested_k_percent"]


def test_frontend_risk_entities_and_detail_expose_horizons_detectors_and_explanations() -> None:
    client = TestClient(app)

    list_response = client.get("/api/v1/risk-entities")
    assert list_response.status_code == 200
    entities = list_response.json()["entities"]
    assert entities
    assert entities[0]["business_score"] >= entities[-1]["business_score"]

    detail_response = client.get(f"/api/v1/risk-entities/{entities[0]['entity_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()

    assert detail["entity"]["entity_id"] == entities[0]["entity_id"]
    assert set(detail["horizon_profiles"]) == {"H3", "H6", "H12"}
    for profile in detail["horizon_profiles"].values():
      assert profile["detector_results"]
      assert profile["xgboost_shap"]
      assert profile["detector_narrative"]


def test_frontend_oneshot_returns_repurchase_propensity_payload() -> None:
    response = TestClient(app).get("/api/v1/oneshot-terminals")

    assert response.status_code == 200
    payload = response.json()

    assert payload["summary"]["oneshot_count"] == len(payload["items"])
    assert payload["items"]
    first = payload["items"][0]
    assert 0 <= first["repurchase_propensity"] <= 1
    assert first["expected_repurchase_amount"] > 0


def test_removed_watchlist_page_api_is_not_exposed() -> None:
    response = TestClient(app).get("/api/v1/watchlist")

    assert response.status_code == 404
