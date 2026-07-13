from __future__ import annotations

import pandas as pd

from risk_model_core.repositories import resolve_observation_context_from_rows


def test_expected_probability_month_unavailable_does_not_fallback_to_older_month() -> None:
    contexts = pd.DataFrame(
        [
            {
                "observation_date": "2025-10-15",
                "probability_report_month": "2025-09",
                "probability_batch_available": True,
                "probability_batch_id": "batch-2025-09",
                "probability_batch_dir": "batch-dir-2025-09",
                "detector_run_date": "2025-10-15",
                "detector_run_available": True,
                "detector_run_id": "detector-2025-10-15",
                "available_horizons": "H3;H6;H12",
                "primary_horizon": "H6",
            }
        ]
    )

    payload = resolve_observation_context_from_rows(
        contexts,
        observation_date="2025-12-05",
        requested_horizon="H3",
    )

    assert payload["ready"] is False
    assert payload["observation_date"] == "2025-12-05"
    assert payload["expected_probability_report_month"] == "2025-11"
    assert payload["probability_report_month"] == "2025-11"
    assert payload["effective_probability_report_month"] is None
    assert payload["probability_batch_available"] is False
    assert payload["probability_batch_id"] is None
    assert payload["probability_batch_dir"] is None
    assert payload["context_status"] == "EXPECTED_MONTH_BATCH_UNAVAILABLE"
    assert payload["available_report_months"] == ["2025-09"]
