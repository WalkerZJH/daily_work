from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.services.frontend_page_service import FrontendPageService


def test_probability_trend_reads_one_published_batch_per_month_up_to_current_month(tmp_path: Path) -> None:
    root = tmp_path / "result_batches"
    for month in ["2024-12", *[f"2025-{number:02d}" for number in range(1, 13)], "2026-01"]:
        _write_monthly_batch(root, month, "a-base", probability=float(month[-2:]) / 100, model_artifact_id="model-a")
    _write_monthly_batch(root, "2025-06", "z-current", probability=0.66, model_artifact_id="model-b")
    _write_monthly_batch(root, "2025-07", "z-current", probability=None, model_artifact_id="model-b")
    _write_monthly_batch(root, "2025-08", "z-current", probability=0.88, manufacturer_code="M2", model_artifact_id="model-b")

    current = root / "report_month=2025-12" / "batch_id=a-base"
    payload = FrontendPageService(batch_dir=current, batch_root=root).probability_trend("risk-1", horizon="H6")

    assert [item["report_month"] for item in payload["items"]] == [
        "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06", "2025-09", "2025-10", "2025-11", "2025-12"
    ]
    assert payload["items"][5]["risk_probability"] == 0.66
    assert all(item["horizon"] == "H6" for item in payload["items"])
    assert all(item["result_batch_id"] for item in payload["items"])
    assert "HISTORICAL_RISK_PROBABILITY_UNAVAILABLE" in payload["warnings"]
    assert "HISTORICAL_RISK_ENTITY_SCOPE_MISMATCH" in payload["warnings"]
    assert "TREND_MODEL_ARTIFACT_CHANGED" in payload["warnings"]


def _write_monthly_batch(
    root: Path,
    report_month: str,
    batch_id: str,
    *,
    probability: float | None,
    manufacturer_code: str = "M1",
    model_artifact_id: str,
) -> None:
    batch = root / f"report_month={report_month}" / f"batch_id={batch_id}"
    batch.mkdir(parents=True, exist_ok=True)
    (batch / "manifest.json").write_text(
        json.dumps(
            {
                "batch_id": batch_id,
                "report_type": "monthly",
                "report_month": report_month,
                "report_date": f"{report_month}-01",
                "score_cutoff_month": report_month,
                "primary_horizon": "H6",
                "available_horizons": ["H3", "H6", "H12"],
                "schema_version": "risk_result_batch_monthly_v2",
                "data_backend": "parquet",
                "allowed_usage": ["internal_diagnostic"],
                "forbidden_usage": ["auto_dispatch"],
                "customer_facing_probability_service_allowed": False,
                "auto_dispatch_allowed": False,
                "proof_case_report_allowed": False,
                "caveats": [],
                "model_artifact_id": model_artifact_id,
                "horizon_profile_table": {"path": "risk_entity_horizon_profiles.parquet"},
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "risk_entity_id": "risk-1",
                "manufacturer_code": manufacturer_code,
                "hospital_code": "H1",
                "drug_code": "D1",
                "report_month": report_month,
            }
        ]
    ).to_parquet(batch / "risk_entities.parquet", index=False)
    pd.DataFrame(
        [
            {
                "risk_entity_id": "risk-1",
                "report_month": report_month,
                "horizon": "H6",
                "risk_probability": probability,
                "involved_amount": 100,
                "involved_amount_source": "fixture",
                "reason": "fixture",
                "updated_at": f"{report_month}-01T00:00:00Z",
            }
        ]
    ).to_parquet(batch / "risk_entity_horizon_profiles.parquet", index=False)
