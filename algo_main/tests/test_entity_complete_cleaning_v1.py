from __future__ import annotations

import pandas as pd

from alg.tasks.die_prediction.entity_complete_rebuild import (
    cleaned_entity_coverage_profile,
    dedupe_raw_orders,
)


def test_dedupe_raw_orders_uses_order_detail_key() -> None:
    raw = pd.DataFrame(
        {
            "raw_order_id": ["o1", "o1", "o2"],
            "value": [1, 1, 2],
        }
    )

    out = dedupe_raw_orders(raw, {"order_detail_id": "raw_order_id"})

    assert len(out) == 2


def test_cleaned_entity_coverage_profile_key_counts_and_null_rates() -> None:
    model_base = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m1", None],
            "hospital_code": ["h1", "h1", "h2"],
            "drug_code": ["d1", "d1", "d2"],
            "purchase_time": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
            "order_detail_id": ["o1", "o2", "o2"],
        }
    )

    profile = cleaned_entity_coverage_profile(model_base)
    values = dict(zip(profile["metric"], profile["value"]))

    assert values["row_count"] == 3
    assert values["entity_count"] == 2
    assert values["manufacturer_code_null_rate"] > 0
    assert values["duplicate_order_detail_id_count"] == 1

