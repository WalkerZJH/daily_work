from __future__ import annotations

from risk_model_core.page_payload_builder import build_default_frontend_payloads


def test_default_workbench_payload_is_twenty_rows_and_sorted() -> None:
    payload = build_default_frontend_payloads()["workbench"]
    rows = payload["rows"]

    assert len(rows) == 20
    assert payload["fill_policy"]["workbench_target_count"] == 20
    assert rows[0]["business_score"] >= rows[-1]["business_score"]
    assert all(row["business_score"] == round(row["risk_probability"] * row["average_consumption_in_window"]) for row in rows)


def test_default_detail_payload_contains_all_horizons_and_detector_context() -> None:
    payloads = build_default_frontend_payloads()
    entity_id = payloads["risk_entities"]["entities"][0]["entity_id"]
    detail = payloads["risk_entity_details"][entity_id]

    assert set(detail["horizon_profiles"]) == {"H3", "H6", "H12"}
    for profile in detail["horizon_profiles"].values():
        assert profile["detector_results"]
        assert profile["xgboost_shap"]
        assert profile["detector_narrative"]


def test_default_oneshot_payload_exposes_repurchase_propensity() -> None:
    payload = build_default_frontend_payloads()["oneshot_terminals"]

    assert payload["summary"]["oneshot_count"] == len(payload["items"])
    assert payload["items"]
    assert 0 <= payload["items"][0]["repurchase_propensity"] <= 1
