"""Source-of-truth purchase-event fact construction for risk_algorithm_core.

This module is a production-safe migration of the v2 exploration fact builder.
It does not import the exploration workspace.
"""

from __future__ import annotations

import pandas as pd


ENTITY_KEYS = ["manufacturer_code", "hospital_code", "drug_group"]


def to_month_end(values: pd.Series | pd.Timestamp | str) -> pd.Series | pd.Timestamp:
    parsed = pd.to_datetime(values, errors="coerce")
    if isinstance(parsed, pd.Series):
        return parsed.dt.to_period("M").dt.to_timestamp("M")
    if pd.isna(parsed):
        return pd.NaT
    return parsed.to_period("M").to_timestamp("M")


def build_fact_purchase_event_from_orders(orders: pd.DataFrame, drug_group_source: str = "drug_code") -> pd.DataFrame:
    """Build one row per valid purchase event from normalized order rows.

    Source-of-truth parity note: the exploration builder treated a valid
    purchase event as non-null purchase time plus valid order detail id. It did
    not drop rows solely because quantity was zero.
    """

    required = {"order_date", "order_id", "manufacturer_code", "hospital_code", drug_group_source}
    missing = sorted(required.difference(orders.columns))
    if missing:
        raise ValueError(f"orders is missing required columns for fact_purchase_event: {missing}")

    out = orders.copy()
    out["purchase_time"] = pd.to_datetime(out["order_date"], errors="coerce")
    out["order_detail_id"] = out["order_id"].astype("string")
    valid_order_id = out["order_detail_id"].notna() & out["order_detail_id"].str.len().gt(0)
    out = out.loc[out["purchase_time"].notna() & valid_order_id].copy()
    out["purchase_month"] = to_month_end(out["purchase_time"])
    out["drug_group"] = out[drug_group_source].astype("string")
    out["drug_group_source"] = drug_group_source

    out["row_uid"] = out.get("row_uid", out["order_detail_id"]).astype("string")
    out["drug_code"] = out.get("drug_code", out["drug_group"]).astype("string")
    out["raw_sensitive_purchase_quantity"] = _numeric_first(out, ["raw_sensitive_purchase_quantity", "order_quantity"])
    out["raw_sensitive_purchase_amount"] = _numeric_first(out, ["raw_sensitive_purchase_amount", "order_amount"])
    out["raw_sensitive_delivery_quantity"] = _numeric_first(out, ["raw_sensitive_delivery_quantity"])
    out["raw_sensitive_arrival_quantity"] = _numeric_first(out, ["raw_sensitive_arrival_quantity"])
    out["order_phase_code"] = _numeric_first(out, ["order_phase_code", "order_status"])
    out["delivery_state_code"] = _numeric_first(out, ["delivery_state_code", "delivery_status"])
    out["order_failure_flag"] = _failure_flag(out)
    out["order_terminal_flag"] = _terminal_flag(out)

    for col in [
        "drug_category_code",
        "province_code",
        "city_code",
        "county_code",
        "hospital_level_code",
        "ownership_type_code",
    ]:
        if col not in out.columns:
            out[col] = pd.NA

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
    return out[[c for c in columns if c in out.columns]].reset_index(drop=True)


def _numeric_first(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    for col in columns:
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce")
    return pd.Series(pd.NA, index=df.index, dtype="Float64")


def _failure_flag(df: pd.DataFrame) -> pd.Series:
    if "order_failure_flag" in df.columns:
        return pd.to_numeric(df["order_failure_flag"], errors="coerce").fillna(0).astype(int)
    status = df.get("order_status", pd.Series("", index=df.index)).astype(str).str.lower()
    return status.str.contains("fail|reject|cancel", regex=True, na=False).astype(int)


def _terminal_flag(df: pd.DataFrame) -> pd.Series:
    if "order_terminal_flag" in df.columns:
        return pd.to_numeric(df["order_terminal_flag"], errors="coerce").fillna(0).astype(int)
    return pd.Series(1, index=df.index, dtype="int64")
