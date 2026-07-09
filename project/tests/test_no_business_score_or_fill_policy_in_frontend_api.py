from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from frontend_api_test_utils import override_frontend_result_repository


def test_frontend_workbench_api_has_no_business_score_or_fill_policy() -> None:
    with override_frontend_result_repository():
        response = TestClient(app).get("/api/v1/workbench", params={"sort_by": "loss_value"})

    assert response.status_code == 200
    text = response.text
    assert "business_score" not in text
    assert "fill_policy" not in text
    assert "risk_probability * average_consumption_in_window" not in text


def test_formal_frontend_paths_do_not_import_algo_runtime_or_raw_source_db() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sources = [
        project_root / "app" / "api" / "routes_frontend_pages.py",
        project_root / "app" / "api" / "routes_detector_results.py",
        project_root / "app" / "api" / "routes_display_lookup.py",
        project_root / "app" / "services" / "frontend_top_entity_adapter.py",
        project_root / "app" / "services" / "detector_result_service.py",
        project_root / "app" / "services" / "display_lookup_service.py",
        project_root / "app" / "services" / "user_top_entity_service.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    for forbidden in [
        "import algo_main",
        "from algo_main",
        "import risk_algorithm_core",
        "from risk_algorithm_core",
        "DATABASE_URL",
        "sql_table_adapter",
        "backbone_service",
    ]:
        assert forbidden not in text
    assert "front_end" not in text
