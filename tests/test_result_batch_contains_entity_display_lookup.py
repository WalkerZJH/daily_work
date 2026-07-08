from __future__ import annotations

from pathlib import Path

import pandas as pd

from risk_result_contracts import validate_result_batch
from risk_result_contracts.schemas import ENTITY_DISPLAY_LOOKUP_REQUIRED_COLUMNS, STANDARD_TABLES


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = (
    ROOT
    / "algo_main"
    / "data"
    / "entity_complete_v2_coverage_expansion"
    / "13_formal_algorithm_core_raw_to_batch"
    / "formal_result_batches"
    / "report_month=2025-12"
    / "batch_id=2025-12-monthly-risk-algorithm-formal-v2-raw"
)


def test_entity_display_lookup_is_standard_result_batch_table() -> None:
    assert "entity_display_lookup" in STANDARD_TABLES


def test_formal_batch_contains_valid_entity_display_lookup() -> None:
    validate_result_batch(BATCH_DIR)
    csv = BATCH_DIR / "entity_display_lookup.csv"
    parquet = BATCH_DIR / "entity_display_lookup.parquet"
    assert csv.exists() or parquet.exists()
    lookup = pd.read_csv(csv) if csv.exists() else pd.read_parquet(parquet)
    assert set(ENTITY_DISPLAY_LOOKUP_REQUIRED_COLUMNS).issubset(lookup.columns)
    assert len(lookup) > 0
    key = ["tenant_id", "report_month", "manufacturer_code", "hospital_code", "drug_group"]
    assert not lookup.duplicated(key).any()
    assert lookup["display_name_quality"].isin(["master", "order", "result_batch", "code_fallback", "mixed"]).all()
