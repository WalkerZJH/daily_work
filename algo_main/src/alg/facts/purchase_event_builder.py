"""Build purchase-event facts for BS_Agent_DingDan alive prediction."""

from __future__ import annotations

import pandas as pd

from alg.utils.months import to_month_end


ENTITY_KEYS = ["manufacturer_code", "hospital_code", "drug_group"]


def build_fact_purchase_event(
    model_base: pd.DataFrame,
    drug_group_source: str = "drug_code",
) -> pd.DataFrame:
    """Build one row per valid purchase event.

    A purchase event is defined as `purchase_time` non-null and
    `order_detail_id` valid. Order status does not negate the event in v1.
    """

    required = {"purchase_time", "order_detail_id", "manufacturer_code", "hospital_code", drug_group_source}
    missing = sorted(required.difference(model_base.columns))
    if missing:
        raise ValueError(f"model_base is missing required columns: {missing}")

    out = model_base.copy()
    out["purchase_time"] = pd.to_datetime(out["purchase_time"], errors="coerce")
    valid_order_id = out["order_detail_id"].notna() & (out["order_detail_id"].astype("string").str.len() > 0)
    out = out.loc[out["purchase_time"].notna() & valid_order_id].copy()
    out["purchase_month"] = to_month_end(out["purchase_time"])
    out["drug_group"] = out[drug_group_source].astype("string")
    out["drug_group_source"] = drug_group_source

    columns = [
        "row_uid",
        "order_detail_id",
        "manufacturer_code",
        "hospital_code",
        "drug_code",
        "drug_category_code",
        "drug_group",
        "drug_group_source",
        "province_code",
        "city_code",
        "county_code",
        "hospital_level_code",
        "ownership_type_code",
        "purchase_time",
        "purchase_month",
        "raw_sensitive_purchase_quantity",
        "raw_sensitive_purchase_amount",
        "raw_sensitive_delivery_quantity",
        "raw_sensitive_arrival_quantity",
        "order_phase_code",
        "delivery_state_code",
        "order_failure_flag",
        "order_terminal_flag",
    ]
    return out[[column for column in columns if column in out.columns]].reset_index(drop=True)
