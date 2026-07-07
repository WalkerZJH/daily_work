from __future__ import annotations

from risk_algorithm_core.entity_builder import build_monthly_entities
from risk_algorithm_core.normalization import normalize_raw_tables
from risk_algorithm_core.raw_input import read_raw_input_batch
from tests.risk_algorithm_core_test_utils import RAW_FIXTURE, SCHEMA_MAPPING


def test_entity_builder_from_orders() -> None:
    batch = read_raw_input_batch(RAW_FIXTURE, SCHEMA_MAPPING)
    normalized, _ = normalize_raw_tables(batch.tables, "2026-07-31")
    entities = build_monthly_entities(
        normalized["orders"],
        normalized["drug_master"],
        normalized["hospital_master"],
        normalized["product_line_mapping"],
        "2026-07",
        "2026-07-31",
        ["H3", "H6", "H12"],
    )
    assert not entities.empty
    assert {"manufacturer_code", "hospital_code", "drug_group", "horizon", "entity_id"}.issubset(entities.columns)
    assert set(entities["drug_group_source"]) == {"drug_code"}
