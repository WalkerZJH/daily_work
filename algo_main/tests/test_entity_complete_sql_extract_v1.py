from __future__ import annotations

import pandas as pd

from alg.tasks.die_prediction.entity_complete_rebuild import (
    entity_history_completeness_after_extract,
    mask_database_url,
    select_entity_keys,
    select_hospital_drug_choice_pairs,
    select_manufacturers,
)


def test_sql_mask_does_not_leak_password() -> None:
    masked = mask_database_url("mssql+pyodbc://user:dummy-value@example/db")

    assert "dummy-value" not in masked
    assert "<user>" in masked
    assert "<host>" in masked


def test_select_manufacturers_prefers_stable_multi_manufacturer_subset() -> None:
    profile = pd.DataFrame(
        {
            "manufacturer_code": ["m0", "m1", "m2", "m3", "m4"],
            "sql_row_count": [900_000, 160_000, 120_000, 95_000, 20_000],
            "entity_count": [9000, 3000, 2500, 2000, 500],
            "active_months_2020_2026": [78, 78, 76, 72, 20],
        }
    )

    selected = select_manufacturers(profile, max_manufacturers=3, min_rows=200_000, target_rows=350_000)

    assert len(selected) >= 3
    assert selected["sql_row_count"].sum() >= 200_000


def test_entity_complete_selection_and_coverage_do_not_truncate_selected_history() -> None:
    entity_profile = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m1", "m2", "m3"],
            "hospital_code": ["h1", "h2", "h3", "h4"],
            "drug_code": ["d1", "d2", "d3", "d4"],
            "sql_order_count_total": [20, 1, 5, 2],
            "sql_first_purchase_time": pd.to_datetime(["2020-01-01"] * 4),
            "sql_last_purchase_time": pd.to_datetime(["2025-01-01"] * 4),
            "sql_active_month_count": [12, 1, 5, 2],
            "sql_months_observed": [61, 1, 10, 2],
        }
    )
    selected_mfg = pd.DataFrame({"manufacturer_code": ["m1"], "sql_row_count": [21], "entity_count": [2]})
    selected_entities = select_entity_keys(entity_profile, selected_mfg, max_entities=3)
    selected_pairs = select_hospital_drug_choice_pairs(entity_profile, selected_mfg, max_pairs=2)

    audit = entity_history_completeness_after_extract(
        entity_profile,
        selected_mfg,
        selected_entities,
        21,
        7,
        selected_pairs=selected_pairs,
        hospital_drug_rows=30,
    )

    assert {"manufacturer_code", "hospital_code", "drug_code"}.issubset(selected_entities.columns)
    assert {"hospital_code", "drug_code"}.issubset(selected_pairs.columns)
    assert audit["entity_history_complete_rate_after_extract"].iloc[0] > 0


def test_hospital_drug_choice_pairs_prioritize_substitution() -> None:
    entity_profile = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m2", "m1"],
            "hospital_code": ["h1", "h1", "h2"],
            "drug_code": ["d1", "d1", "d2"],
            "sql_order_count_total": [10, 5, 3],
            "sql_active_month_count": [4, 3, 2],
            "sql_months_observed": [10, 8, 5],
        }
    )
    selected_mfg = pd.DataFrame({"manufacturer_code": ["m1"]})

    pairs = select_hospital_drug_choice_pairs(entity_profile, selected_mfg, max_pairs=2)

    sub_pair = pairs[(pairs["hospital_code"].eq("h1")) & (pairs["drug_code"].eq("d1"))].iloc[0]
    assert bool(sub_pair["has_manufacturer_substitution"]) is True
