from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from app.api.routes_report_context import get_report_context_service
from app.main import app
from app.services.report_context_service import ReportContextService
from detector_result_test_utils import override_detector_service


class _RegistryRepository:
    def list_available_observation_contexts(self, *, batch_root: Path) -> pd.DataFrame:
        dates = pd.date_range("2025-01-01", "2025-12-31", freq="D").strftime("%Y-%m-%d")
        return pd.DataFrame(
            {
                "detector_run_date": [*dates, "2026-01-01"],
                "detector_run_available": True,
                "detector_run_id": "component-view",
                "probability_report_month": "2025-12",
            }
        )


def test_daily_detector_dates_exposes_full_registry_without_component_duplicates() -> None:
    service = ReportContextService(_RegistryRepository(), batch_root=Path("formal-root"))
    app.dependency_overrides[get_report_context_service] = lambda: service
    try:
        with override_detector_service():
            response = TestClient(app).get("/api/v1/daily-detector/dates", params={"limit": 500})
    finally:
        app.dependency_overrides.pop(get_report_context_service, None)

    assert response.status_code == 200
    payload = response.json()
    dates = [item["run_date"] for item in payload["items"]]
    dates_2025 = [date for date in dates if date.startswith("2025-")]
    assert payload["source"] == "observation_registry"
    assert len(dates_2025) == 365
    assert dates_2025[0] == "2025-12-31"
    assert dates_2025[-1] == "2025-01-01"
    assert len(dates_2025) == len(set(dates_2025))
