from __future__ import annotations

from risk_algorithm_core.entity_builder import build_monthly_entities
from risk_algorithm_core.feature_engineering import engineer_features
from risk_algorithm_core.normalization import normalize_raw_tables
from risk_algorithm_core.raw_input import read_raw_input_batch
from tests.risk_algorithm_core_test_utils import RAW_FIXTURE, SCHEMA_MAPPING


def test_feature_engineering_builds_asof_features() -> None:
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
    features, report = engineer_features(entities, normalized["orders"], "2026-07-31")
    assert len(features) == len(entities)
    for col in ["months_since_last_purchase", "frequency_ratio", "current_interval_over_median", "quantity_ratio", "demand_shape_label"]:
        assert col in features.columns
    assert report.loc[report["metric"].eq("feature_rows"), "value"].iloc[0] == len(features)
