from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from frontend_api_test_utils import override_frontend_result_repository


def test_workbench_returns_new_contract_without_legacy_fields_or_copy() -> None:
    with override_frontend_result_repository():
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={
                "manufacturer_code": "M1",
                "report_month": "2025-12",
                "run_date": "2025-12-31",
                "horizon": "H6",
                "top_n": 2,
                "sort_by": "loss_value",
                "user_id": "frontend_user",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["current_manufacturer_code"] == "M1"
    assert payload["current_observation_date"] == "2025-12-31"
    assert payload["horizon"] == "H6"
    assert payload["top_n"] == 2
    assert payload["sort_by"] == "loss_value"
    assert payload["today_clue_count"] == 2
    assert payload["highest_detector_score"] == 0.82
    assert payload["priority_risk_entity_count"] == 2
    assert 1 <= len(payload["today_high_score_rule_clues"]) <= 5
    assert len(payload["monthly_risk_entities"]) <= 2
    assert payload["monthly_risk_entities"][0]["loss_value"] == 800
    assert payload["monthly_risk_entities"][0]["loss_value_status"] == "ready"

    text = json.dumps(payload, ensure_ascii=False)
    for forbidden in [
        "fill_policy",
        "business_score",
        "risk_probability * average_consumption_in_window",
        "主工作台",
        "风险卡",
        "新进终端",
        "高价值待跟进",
        "补齐",
        "回补",
        "补充算法",
        "新进终端补齐",
        "规则巡检补充",
        "历史节奏回补",
        "MonthlyReport",
        "RiskResultBatch",
        "oneshot",
        "模型关键指标",
        "AUC",
        "ECE",
        "PR-AUC",
        "XGBoost",
        "CatBoost",
        "LightGBM",
    ]:
        assert forbidden not in text


def test_workbench_accepts_detector_score_sort_param_without_recomputing_detector() -> None:
    with override_frontend_result_repository():
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={"horizon": "H6", "top_n": 1, "sort_by": "detector_score"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sort_by"] == "detector_score"
    assert payload["data_source"] == "risk_model_core"
    assert "mock" not in json.dumps(payload).lower()
