from __future__ import annotations

import json

import pandas as pd

from fastapi.testclient import TestClient

from app.main import app
from frontend_api_test_utils import empty_daily_detector_clues, make_frontend_repository, override_frontend_result_repository


def test_daily_detector_clues_returns_200_empty_list_when_no_clues() -> None:
    repository = make_frontend_repository(clues=empty_daily_detector_clues())
    with override_frontend_result_repository(repository):
        response = TestClient(app).get(
            "/api/v1/daily-detector/clues",
            params={
                "manufacturer_code": "M1",
                "run_date": "2025-12-31",
                "horizon": "H6",
                "top_n": 5,
                "sort_by": "detector_score",
                "only_monthly_high_risk": False,
                "page": 1,
                "page_size": 20,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["total"] == 0
    assert payload["items"] == []
    assert payload["clues"] == []
    assert payload["run_date"] == "2025-12-31"
    assert payload["detector_run_id"] == "run_2025_12_31"
    assert "mock" not in json.dumps(payload).lower()


def test_daily_detector_clues_returns_only_detector_hits() -> None:
    repository = make_frontend_repository()
    non_hit = repository.load_table("daily_detector_clues").iloc[[0]].copy()
    non_hit["detector_clue_id"] = "clue_not_hit"
    non_hit["hit_flag"] = False
    repository.tables["daily_detector_clues"] = pd.concat(
        [repository.load_table("daily_detector_clues"), non_hit], ignore_index=True
    )

    with override_frontend_result_repository(repository):
        response = TestClient(app).get("/api/v1/daily-detector/clues", params={"sort_by": "detector_score"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert {item["detector_clue_id"] for item in payload["clues"]} == {"clue_high", "clue_rule_only"}
    assert all(item["hit_flag"] is True for item in payload["clues"])


def test_daily_detector_clues_deduplicates_detector_clue_id() -> None:
    repository = make_frontend_repository()
    duplicate = repository.load_table("daily_detector_clues").iloc[[0]].copy()
    repository.tables["daily_detector_clues"] = pd.concat(
        [repository.load_table("daily_detector_clues"), duplicate], ignore_index=True
    )

    with override_frontend_result_repository(repository):
        response = TestClient(app).get("/api/v1/daily-detector/clues", params={"sort_by": "detector_score"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert len({item["detector_clue_id"] for item in payload["items"]}) == payload["total"]


def test_daily_detector_clues_labels_non_monthly_high_risk_as_rule_only() -> None:
    with override_frontend_result_repository():
        response = TestClient(app).get(
            "/api/v1/daily-detector/clues",
            params={"only_monthly_high_risk": False, "sort_by": "detector_score"},
        )

    assert response.status_code == 200
    payload = response.json()
    rule_only = next(item for item in payload["clues"] if item["clue_id"] == "clue_rule_only")
    assert rule_only["is_monthly_high_risk_entity"] is False
    assert rule_only["action"] == "仅规则命中"
    assert rule_only["detector_score_label"] == "规则巡检分"
    assert "detector_probability" not in json.dumps(payload)
