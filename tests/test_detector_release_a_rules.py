from __future__ import annotations

import json

import pandas as pd
import pytest

from production_pipeline.detector_input_snapshot import build_detector_input_snapshot
from production_pipeline.run_daily_detector import materialize_detector_component_batch
from risk_algorithm_core.daily_detector_runner import build_daily_detector_tables
from risk_algorithm_core.detector_config import load_daily_detector_config
from risk_algorithm_core.detector_config_profiles import build_manufacturer_config_profiles


def _all_rule_features() -> pd.DataFrame:
    common = {
        "tenant_id": "default_tenant",
        "manufacturer_code": "m1",
        "observation_date": "2026-07-16",
        "purchase_unit": "盒",
        "purchase_count_total": 12,
        "recent_window_start": "2026-04-17",
        "recent_window_end": "2026-07-16",
        "baseline_window_start": "2025-07-16",
        "baseline_window_end": "2026-04-17",
        "data_history_start": "2025-01-01",
        "entity_purchase_unit_count": 1,
        "demand_shape_label": "smooth",
        "current_purchase_flag": True,
        "current_order_count": 1,
        "current_order_id": "order-current",
        "reference_order_count": 100,
        "reference_hospital_count": 10,
    }
    return pd.DataFrame(
        [
            {
                **common,
                "entity_id": "m1|h1|d1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "days_since_last_purchase": 60,
                "historical_interval_median": 10,
                "historical_interval_mad": 5,
                "recent_quantity": 6,
                "baseline_quantity": 100,
                "quantity_ratio": 0.18,
                "recent_amount": 30,
                "baseline_amount": 1000,
                "amount_ratio": 0.09,
                "recent_order_count": 1,
                "baseline_order_count": 18,
                "recent_frequency": 1 / 3,
                "purchase_frequency_baseline": 2,
                "frequency_ratio": 1 / 6,
                "current_unit_price": 5,
                "market_reference_price": 10,
                "price_recent_order_count": 5,
                "price_baseline_order_count": 10,
                "min_price": 5,
                "max_price": 10,
                "median_price": 7,
                "price_spread_ratio": 2,
                "recent_price": 6,
                "baseline_price": 10,
                "price_ratio": 0.6,
                "first_purchase_date": "2026-07-16",
                "first_order_id": "order-current",
                "first_purchase_quantity": 6,
                "first_purchase_amount": 30,
                "previous_purchase_date": "2025-12-01",
                "silence_days": 227,
            },
            {
                **common,
                "entity_id": "m1|h2|d2",
                "hospital_code": "h2",
                "drug_group": "d2",
                "days_since_last_purchase": 0,
                "historical_interval_median": 30,
                "historical_interval_mad": 5,
                "recent_quantity": 120,
                "baseline_quantity": 90,
                "quantity_ratio": 4,
                "recent_amount": 1200,
                "baseline_amount": 900,
                "amount_ratio": 4,
                "recent_order_count": 18,
                "baseline_order_count": 18,
                "recent_frequency": 6,
                "purchase_frequency_baseline": 2,
                "frequency_ratio": 3,
                "current_unit_price": 10,
                "market_reference_price": 5,
                "price_recent_order_count": 1,
                "price_baseline_order_count": 1,
                "min_price": 10,
                "max_price": 10,
                "median_price": 10,
                "price_spread_ratio": 1,
                "recent_price": 10,
                "baseline_price": 10,
                "price_ratio": 1,
                "first_purchase_date": "2025-01-01",
                "previous_purchase_date": "2026-07-01",
                "silence_days": 15,
            },
        ]
    )


def test_all_ten_non_delivery_detectors_have_executable_results_and_hits() -> None:
    tables = build_daily_detector_tables(
        risk_entities=pd.DataFrame(),
        scan_features=_all_rule_features(),
        report_month="2026-06",
        run_date="2026-07-16",
        source_raw_batch_id="clean-input",
    )
    results = tables["daily_detector_results"]
    clues = tables["daily_detector_clues"]
    expected = set(load_daily_detector_config().runnable_detector_ids())
    assert set(results["detector_id"]) == expected
    assert set(clues["detector_id"]) == expected
    assert len(results) == 20
    assert results["config_id"].astype(str).str.startswith("cfg-").all()
    assert results["config_hash"].astype(str).str.len().eq(64).all()
    assert "detector_probability" not in results.columns
    assert not set(results["detector_family"]).intersection({"fulfillment", "assortment"})

    quantity = clues.loc[clues["detector_id"].eq("purchase_quantity_trend")].iloc[0]
    payload = json.loads(quantity["evidence_payload"])
    assert payload["method"] == "simplified_ratio_v1"
    assert payload["amount_direction_consistent"] is True
    assert payload["demand_shape_label"] == "smooth"
    low_price = clues.loc[clues["detector_id"].eq("low_price_warning")].iloc[0]
    assert json.loads(low_price["evidence_payload"])["threshold_source"] == "prior_market_p05"
    assert "竞争" not in low_price["evidence_text"]


def test_price_reference_is_grouped_by_drug_and_cleaned_purchase_unit() -> None:
    orders = pd.DataFrame(
        [
            {"order_date": "2026-01-01", "order_id": "a", "manufacturer_code": "m1", "hospital_code": "h1", "drug_code": "d1", "order_quantity": 1, "order_amount": 10, "purchase_unit": "盒", "purchase_unit_price": 10},
            {"order_date": "2026-01-01", "order_id": "b", "manufacturer_code": "m2", "hospital_code": "h2", "drug_code": "d1", "order_quantity": 1, "order_amount": 100, "purchase_unit": "瓶", "purchase_unit_price": 100},
            {"order_date": "2026-07-16", "order_id": "c", "manufacturer_code": "m1", "hospital_code": "h1", "drug_code": "d1", "order_quantity": 1, "order_amount": 5, "purchase_unit": "盒", "purchase_unit_price": 5},
        ]
    )
    snapshot = build_detector_input_snapshot(orders, "2026-07-16")
    box = snapshot.loc[snapshot["manufacturer_code"].eq("m1")].iloc[0]
    bottle = snapshot.loc[snapshot["manufacturer_code"].eq("m2")].iloc[0]
    assert box["market_reference_price"] == 10
    assert bottle["market_reference_price"] == 100


def test_component_publish_blocks_missing_manufacturer_profile(tmp_path) -> None:
    config = load_daily_detector_config()
    profiles = build_manufacturer_config_profiles(
        ["m1"], config, detector_ids=["purchase_interval_ipi"]
    )
    snapshot = _all_rule_features().copy()
    snapshot["manufacturer_code"] = "m2"
    with pytest.raises(ValueError, match="configs are missing"):
        materialize_detector_component_batch(
            snapshot_frame=snapshot,
            output_root=tmp_path,
            observation_date="2026-07-16",
            detector_id="purchase_interval_ipi",
            run_id="missing-config",
            raw_batch_id="clean-input",
            config_profiles=profiles,
        )
    assert not list(tmp_path.glob("detector_run_date=*/detector_id=*/batch_id=*"))
