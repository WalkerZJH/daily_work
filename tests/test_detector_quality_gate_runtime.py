from __future__ import annotations

from risk_algorithm_core.detector_quality_gate import DetectorQualityGate
from risk_algorithm_core.entity_builder import build_monthly_entities
from risk_algorithm_core.feature_engineering import engineer_features
from risk_algorithm_core.normalization import normalize_raw_tables
from risk_algorithm_core.raw_input import read_raw_input_batch
from tests.risk_algorithm_core_test_utils import RAW_FIXTURE, SCHEMA_MAPPING


def test_detector_quality_gate_disables_delivery_and_price_by_default() -> None:
    batch = read_raw_input_batch(RAW_FIXTURE, SCHEMA_MAPPING)
    normalized, _ = normalize_raw_tables(batch.tables, "2026-07-31")
    entities = build_monthly_entities(
        normalized["orders"],
        normalized["drug_master"],
        normalized["hospital_master"],
        normalized["product_line_mapping"],
        "2026-07",
        "2026-07-31",
        ["H6"],
    )
    features, _ = engineer_features(entities, normalized["orders"], "2026-07-31")
    gates = DetectorQualityGate({}).evaluate(features, normalized)
    by_name = gates.set_index("detector_name")
    assert by_name.loc["purchase_interval_overdue_warning", "gate_status"] == "enabled_rule_v1"
    assert by_name.loc["purchase_frequency_fluctuation_warning", "gate_status"] == "enabled_rule_v1"
    assert by_name.loc["delayed_response_warning", "gate_status"] == "deferred_missing_data"
    assert by_name.loc["low_price_purchase_warning", "gate_status"] == "interface_only"
    assert "responsibility" in by_name.loc["low_delivery_rate_warning", "semantic_caveat"]
