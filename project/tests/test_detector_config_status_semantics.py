from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from detector_result_test_utils import override_detector_service


def test_detector_config_status_explains_next_run_semantics_without_rewriting_runs() -> None:
    with override_detector_service():
        response = TestClient(app).get("/api/v1/detectors/config-status")

    assert response.status_code == 200
    payload = response.json()

    assert payload["effective_config_version"] == "daily_detector_rules_v1"
    assert payload["latest_run_id"] == "run_2025_12_31"
    assert payload["latest_run_date"] == "2025-12-31"
    assert payload["pending_config_exists"] is False
    assert payload["pending_config_supported"] is False
    assert payload["next_run_required"] is False
    assert "下一次 detector 巡检运行后生效" in payload["config_edit_semantics"]
    assert payload["history_rewrite_allowed"] is False
