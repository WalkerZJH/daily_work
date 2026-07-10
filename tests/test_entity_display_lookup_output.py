from __future__ import annotations

import pandas as pd

from risk_algorithm_core.entity_display_lookup import (
    ENTITY_DISPLAY_LOOKUP_COLUMNS,
    build_entity_display_lookup,
)


def test_entity_display_lookup_prefers_master_names_and_marks_code_fallback() -> None:
    risk_entities = pd.DataFrame(
        [
            {
                "tenant_id": "tenant",
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_code": "d1",
                "drug_group": "d1",
                "report_month": "2025-12",
            },
            {
                "tenant_id": "tenant",
                "manufacturer_code": "m2",
                "hospital_code": "h_missing",
                "drug_code": "d_missing",
                "drug_group": "d_missing",
                "report_month": "2025-12",
            },
        ]
    )
    normalized = {
        "orders": pd.DataFrame(
            [
                {"manufacturer_code": "m1", "hospital_code": "h1", "drug_code": "d1", "order_date": "2025-12-01"},
                {"manufacturer_code": "m2", "hospital_code": "h_missing", "drug_code": "d_missing", "order_date": "2025-12-02"},
            ]
        ),
        "hospital_master": pd.DataFrame(
            [{"hospital_code": "h1", "hospital_name": "Hospital One", "region_code": "r1", "region_name": "Region One"}]
        ),
        "drug_master": pd.DataFrame(
            [{"drug_code": "d1", "drug_name": "Drug One", "product_line_code": "pl1", "product_line_name": "Line One"}]
        ),
        "product_line_mapping": pd.DataFrame(
            [{"drug_code": "d1", "product_line_code": "pl1", "product_line_name": "Line One"}]
        ),
    }

    lookup = build_entity_display_lookup(
        risk_entities,
        normalized,
        report_month="2025-12",
        raw_batch_id="raw-001",
        updated_at="2026-07-08T00:00:00+00:00",
    )

    assert list(lookup.columns) == ENTITY_DISPLAY_LOOKUP_COLUMNS
    assert len(lookup) == 2
    assert not lookup.duplicated(["tenant_id", "report_month", "manufacturer_code", "hospital_code", "drug_group"]).any()

    named = lookup[lookup["hospital_code"].eq("h1")].iloc[0]
    assert named["hospital_display_name"] == "Hospital One"
    assert named["drug_display_name"] == "Drug One"
    assert named["product_line_name"] == "Line One"
    assert named["region_display_name"] == "Region One"
    assert named["display_name_quality"] == "master"

    fallback = lookup[lookup["hospital_code"].eq("h_missing")].iloc[0]
    assert fallback["hospital_display_name"] == "h_missing"
    assert fallback["drug_display_name"] == "d_missing"
    assert fallback["display_name_quality"] == "code_fallback"
    assert fallback["source_raw_batch_id"] == "raw-001"


def test_entity_display_lookup_includes_detector_only_entities() -> None:
    risk_entities = pd.DataFrame(
        [
            {
                "tenant_id": "tenant",
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_code": "d1",
                "drug_group": "d1",
                "report_month": "2025-12",
            }
        ]
    )
    detector_entities = pd.DataFrame(
        [
            {
                "tenant_id": "tenant",
                "manufacturer_code": "m1",
                "hospital_code": "h_detector",
                "drug_code": "d_detector",
                "drug_group": "d_detector",
                "hospital_display_name": "Detector Hospital",
                "drug_display_name": "Detector Drug",
                "report_month": "2025-12",
            }
        ]
    )

    lookup = build_entity_display_lookup(
        risk_entities,
        {"manufacturer_master": pd.DataFrame([{"manufacturer_code": "m1", "manufacturer_name": "Manufacturer One"}])},
        report_month="2025-12",
        raw_batch_id="raw-001",
        additional_entities=detector_entities,
        updated_at="2026-07-08T00:00:00+00:00",
    )

    detector_row = lookup[lookup["hospital_code"].eq("h_detector")].iloc[0]
    assert detector_row["manufacturer_display_name"] == "Manufacturer One"
    assert detector_row["hospital_display_name"] == "Detector Hospital"
    assert detector_row["drug_display_name"] == "Detector Drug"
