from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from observation_context_test_utils import configure_formal_observation_env


def test_report_context_accepts_observation_date_and_returns_observation_semantics(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    response = TestClient(app).get(
        "/api/v1/report-context",
        params={"observation_date": "2025-12-05", "horizon": "H6"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["observation_date"] == "2025-12-05"
    assert payload["probability_report_month"] == "2025-11"
    assert payload["probability_batch_available"] is True
    assert payload["detector_run_date"] == "2025-12-05"
    assert payload["detector_run_available"] is True
    assert payload["context_status"] == "ready"
    assert payload["manual_selection_required"] is False
    assert payload["effective_horizon"] == "H6"
    assert "2025-11" in payload["available_report_months"]
    assert "2025-12-05" in payload["available_detector_run_dates"]
    assert "fallback_to_latest" not in json.dumps(payload, ensure_ascii=False)


def test_report_context_observation_date_ignores_stale_report_month_by_default(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    response = TestClient(app).get(
        "/api/v1/report-context",
        params={
            "observation_date": "2025-12-05",
            "report_month": "2025-09",
            "run_date": "2025-12-05",
            "horizon": "H3",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_observation_date"] == "2025-12-05"
    assert payload["effective_observation_date"] == "2025-12-05"
    assert payload["requested_report_month"] == "2025-09"
    assert payload["expected_probability_report_month"] == "2025-11"
    assert payload["effective_probability_report_month"] == "2025-11"
    assert payload["probability_report_month"] == "2025-11"
    assert payload["detector_run_date"] == "2025-12-05"
    assert payload["detector_run_available"] is True
    assert payload["context_status"] == "ready"


def test_report_context_manual_report_month_mode_keeps_explicit_history_month(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    response = TestClient(app).get(
        "/api/v1/report-context",
        params={
            "observation_date": "2025-12-05",
            "report_month": "2025-12",
            "manual_report_month": "true",
            "horizon": "H3",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_report_month"] == "2025-12"
    assert payload["expected_probability_report_month"] == "2025-11"
    assert payload["effective_probability_report_month"] == "2025-12"
    assert payload["probability_report_month"] == "2025-12"
    assert payload["detector_run_date"] == "2025-12-05"
    assert payload["detector_run_available"] is False
    assert payload["context_status"] == "detector_run_unavailable"


def test_report_context_maps_legacy_run_date_to_observation_date(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    response = TestClient(app).get(
        "/api/v1/report-context",
        params={"run_date": "2025-12-05"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["observation_date"] == "2025-12-05"
    assert payload["requested_run_date"] == "2025-12-05"
    assert payload["probability_report_month"] == "2025-11"
    assert payload["detector_run_date"] == "2025-12-05"
