from __future__ import annotations

import json

import pandas as pd
import pytest

from risk_model_core.repositories import ParquetRiskResultRepository


def _write_batch(tmp_path, rows: list[dict]) -> ParquetRiskResultRepository:
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "batch_id": "detail-test",
                "result_batch_id": "detail-test",
                "report_type": "monthly",
                "report_month": "2025-12",
                "report_date": "2025-12-31",
                "score_cutoff_month": "2025-12-31",
                "primary_horizon": "H6",
                "available_horizons": ["H6"],
                "schema_version": "test",
                "data_backend": "parquet",
                "allowed_usage": [],
                "forbidden_usage": [],
                "customer_facing_probability_service_allowed": False,
                "auto_dispatch_allowed": False,
                "proof_case_report_allowed": False,
                "caveats": [],
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(rows).to_parquet(tmp_path / "daily_detector_clues.parquet", index=False)
    return ParquetRiskResultRepository(tmp_path)


def test_detector_clue_detail_uses_projected_parquet_lookup_not_list_or_pandas(monkeypatch, tmp_path) -> None:
    repository = _write_batch(
        tmp_path,
        [{"detector_clue_id": "clue-1", "detector_score": 0.7, "unused": "not requested"}],
    )

    monkeypatch.setattr(repository, "list_daily_detector_clues", lambda **_: pytest.fail("list path must not be used"))
    monkeypatch.setattr(pd, "read_parquet", lambda *_, **__: pytest.fail("pandas parquet path must not be used"))

    row = repository.get_daily_detector_clue_by_id("clue-1", columns=["detector_score"])

    assert row == {"detector_score": 0.7, "detector_clue_id": "clue-1"}


def test_detector_clue_detail_returns_none_or_rejects_duplicate_id(tmp_path) -> None:
    repository = _write_batch(
        tmp_path,
        [
            {"detector_clue_id": "duplicate", "detector_score": 0.7},
            {"detector_clue_id": "duplicate", "detector_score": 0.8},
        ],
    )

    assert repository.get_daily_detector_clue_by_id("missing") is None
    with pytest.raises(ValueError, match="Duplicate detector_clue_id"):
        repository.get_daily_detector_clue_by_id("duplicate")
