from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from detector_result_test_utils import override_detector_service


def test_detector_config_status_declares_read_only_admin_parameters() -> None:
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
    assert payload["history_rewrite_allowed"] is False
    assert payload["parameter_source"] == "admin_parameter_table"
    assert payload["parameter_editable"] is False
    assert payload["personalized_parameter_profiles"] == "deferred_not_implemented"
    assert payload["display_filter_policy"] == "request_only_no_persistence"
    assert "不提供用户参数修改入口" in payload["config_edit_semantics"]
