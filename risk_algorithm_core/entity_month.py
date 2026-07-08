"""Source-of-truth entity-month aggregation for risk_algorithm_core."""

from __future__ import annotations

import pandas as pd

from .facts import ENTITY_KEYS


def build_fact_entity_month(purchase_events: pd.DataFrame) -> pd.DataFrame:
    required = set(ENTITY_KEYS + ["purchase_month", "purchase_time", "order_detail_id"])
    missing = sorted(required.difference(purchase_events.columns))
    if missing:
        raise ValueError(f"purchase_events is missing required columns: {missing}")

    df = purchase_events.copy()
    grouped = df.groupby(ENTITY_KEYS + ["purchase_month"], dropna=False)
    result = grouped.agg(
        order_count=("order_detail_id", "count"),
        has_purchase=("order_detail_id", lambda s: int(s.notna().any())),
        last_purchase_time_in_month=("purchase_time", "max"),
    ).reset_index()

    sum_map = {
        "raw_sensitive_purchase_quantity": "purchase_quantity_sum",
        "raw_sensitive_purchase_amount": "purchase_amount_sum",
        "raw_sensitive_delivery_quantity": "delivery_quantity_sum",
        "raw_sensitive_arrival_quantity": "arrival_quantity_sum",
    }
    for source, target in sum_map.items():
        if source in df.columns:
            result[target] = grouped[source].sum(min_count=1).to_numpy()

    flag_specs = {
        "failed_count": ("order_failure_flag", 1),
        "received_count": ("delivery_state_code", 5),
        "terminal_count": ("order_terminal_flag", 1),
    }
    for target, (source, value) in flag_specs.items():
        if source in df.columns:
            result[target] = grouped[source].apply(lambda s, v=value: int((s == v).sum())).to_numpy()
        else:
            result[target] = 0

    static_columns = [
        "province_code",
        "city_code",
        "county_code",
        "hospital_level_code",
        "ownership_type_code",
        "drug_category_code",
    ]
    for column in static_columns:
        if column in df.columns:
            result[column] = grouped[column].first().to_numpy()

    ordered = df.sort_values("purchase_time")
    last_by_month = ordered.groupby(ENTITY_KEYS + ["purchase_month"], dropna=False).tail(1)
    for column in ["order_phase_code", "delivery_state_code", "order_failure_flag"]:
        if column in last_by_month.columns:
            values = last_by_month.set_index(ENTITY_KEYS + ["purchase_month"])[column]
            result[f"last_{column}_in_month"] = result.set_index(ENTITY_KEYS + ["purchase_month"]).index.map(values)

    return result.sort_values(ENTITY_KEYS + ["purchase_month"]).reset_index(drop=True)
