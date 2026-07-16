from __future__ import annotations

import json

import pandas as pd
import pytest

from production_pipeline.export_cleaned_detector_input import export_cleaned_detector_input
from risk_algorithm_core.detector_input import (
    filter_detector_eligible_orders,
    load_cleaned_detector_orders,
)


def _cleaned_rows() -> pd.DataFrame:
    common = {
        "manufacturer_code": "m1",
        "hospital_code": "h1",
        "drug_code": "d1",
        "purchase_unit": "盒",
        "raw_sensitive_purchase_price": 10.0,
        "raw_sensitive_purchase_quantity": 2.0,
        "raw_sensitive_purchase_amount": 20.0,
        "order_status_raw": "配送完成",
        "order_status_norm": "配送完成",
        "order_terminal_flag": 1,
        "order_failure_flag": 0,
        "needs_manual_review": False,
    }
    return pd.DataFrame(
        [
            {**common, "row_uid": "r1", "order_detail_id": "o1", "purchase_time": "2026-01-01", "order_phase_code": 60},
            {**common, "row_uid": "r2", "order_detail_id": "o2", "purchase_time": "2026-01-02", "order_phase_code": 20, "order_terminal_flag": 0},
            {**common, "row_uid": "r3", "order_detail_id": "o3", "purchase_time": "2026-01-03", "order_phase_code": 100, "order_failure_flag": 1},
        ]
    )


def test_export_uses_one_cleaned_parquet_and_publishes_explicit_contract(tmp_path) -> None:
    clean_path = tmp_path / "clean.parquet"
    _cleaned_rows().to_parquet(clean_path, index=False)
    batch = tmp_path / "detector-input-v1"

    export_cleaned_detector_input(
        cleaned_orders_path=clean_path,
        output_dir=batch,
        input_batch_id="detector-input-v1",
    )

    manifest, orders = load_cleaned_detector_orders(batch)
    assert manifest.input_stage == "cleaned_detector_facts"
    assert len(orders) == 3
    assert orders["purchase_unit"].tolist() == ["盒", "盒", "盒"]
    payload = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))
    assert payload["cleaning_contract"]["cleaned_orders_sha256"]
    assert payload["cleaning_contract"]["cleaned_orders_rows"] == 3
    assert payload["cleaning_contract"]["purchase_unit_from_cleaned_orders"] is True
    assert payload["cleaning_contract"]["raw_business_measure_fallback_allowed"] is False
    assert "purchase_unit_lineage_path" not in payload["cleaning_contract"]


def test_shared_order_filter_allows_only_normal_completed_orders() -> None:
    clean = _cleaned_rows()
    exported = pd.DataFrame(
        {
            "row_uid": clean["row_uid"],
            "order_id": clean["order_detail_id"],
            "order_date": clean["purchase_time"],
            "manufacturer_code": clean["manufacturer_code"],
            "hospital_code": clean["hospital_code"],
            "drug_code": clean["drug_code"],
            "order_quantity": clean["raw_sensitive_purchase_quantity"],
            "order_amount": clean["raw_sensitive_purchase_amount"],
            "purchase_unit": clean["purchase_unit"],
            "purchase_unit_price": clean["raw_sensitive_purchase_price"],
            "order_phase_code": clean["order_phase_code"],
            "order_terminal_flag": clean["order_terminal_flag"],
            "order_failure_flag": clean["order_failure_flag"],
            "needs_manual_review": clean["needs_manual_review"],
        }
    )
    eligible, audit = filter_detector_eligible_orders(exported)
    assert eligible["row_uid"].tolist() == ["r1"]
    assert audit["detector_exclusion_reason"].tolist() == [
        "eligible_normal_completion",
        "not_terminal",
        "failure_or_cancelled_terminal",
    ]


def test_runtime_rejects_raw_or_clickhouse_manifest(tmp_path) -> None:
    (tmp_path / "manifest.json").write_text(
        json.dumps({"raw_batch_id": "dirty", "source_system": "clickhouse", "table_format": "clickhouse"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="cleaned_detector_facts"):
        load_cleaned_detector_orders(tmp_path)
