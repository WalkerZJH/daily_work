from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from detector_result_test_utils import make_detector_repository, override_detector_service


def test_event_aggregate_api_supports_exact_historical_detector_filter() -> None:
    repository = make_detector_repository()
    repository.tables["detector_event_aggregates"] = pd.DataFrame([
        {
            "detector_event_aggregate_id": "a1", "observation_date": "2025-12-31",
            "manufacturer_code": "m1", "hospital_code": "h1", "drug_code": "d1",
            "current_detector_count": 2, "current_detector_ids": "detector_a|detector_aa",
            "cumulative_hit_count": 7, "cumulative_hit_day_count": 4,
            "historical_detector_ids": "detector_a|detector_aa",
            "first_hit_date": "2025-01-01", "last_hit_date": "2025-12-31",
            "aggregation_schema_version": "detector_event_aggregation_v1",
            "generated_at": "2026-01-01T00:00:00+00:00",
        },
        {
            "detector_event_aggregate_id": "a2", "observation_date": "2025-12-31",
            "manufacturer_code": "m1", "hospital_code": "h2", "drug_code": "d2",
            "current_detector_count": 1, "current_detector_ids": "detector_aa",
            "cumulative_hit_count": 9, "cumulative_hit_day_count": 6,
            "historical_detector_ids": "detector_aa",
            "first_hit_date": "2025-02-01", "last_hit_date": "2025-12-31",
            "aggregation_schema_version": "detector_event_aggregation_v1",
            "generated_at": "2026-01-01T00:00:00+00:00",
        },
    ])

    with override_detector_service(repository):
        response = TestClient(app).get("/api/v1/detectors/event-aggregates", params={
            "observation_date": "2025-12-31", "manufacturer_code": "m1",
            "historical_detector_id": "detector_a", "sort_by": "cumulative_hit_count",
        })

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["detector_event_aggregate_id"] == "a1"
    assert payload["items"][0]["current_detector_ids"] == ["detector_a", "detector_aa"]
    assert payload["items"][0]["historical_detector_ids"] == ["detector_a", "detector_aa"]
