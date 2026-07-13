from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from observation_context_test_utils import configure_formal_observation_env


def test_missing_detector_date_is_not_substituted_with_latest_available_run(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    payload = TestClient(app).get(
        "/api/v1/daily-detector/status",
        params={"observation_date": "2025-12-05", "report_month": "2025-12", "manual_report_month": "true"},
    ).json()

    assert payload["detector_run_date"] == "2025-12-05"
    assert payload["effective_run_date"] == "2025-12-05"
    assert payload["run_date"] == "2025-12-05"
    assert payload["detector_run_available"] is False
    assert payload["context_status"] == "detector_run_unavailable"
    assert payload["run_date"] not in {"2025-12-01", "2026-01-01"}
