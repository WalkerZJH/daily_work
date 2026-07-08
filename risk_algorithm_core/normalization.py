"""Normalize raw business tables into standard production algorithm inputs."""

from __future__ import annotations

import pandas as pd


def normalize_orders(orders: pd.DataFrame, cutoff_date: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = orders.copy()
    for col in ["manufacturer_code", "hospital_code", "drug_code", "distributor_code", "order_status", "delivery_status"]:
        if col not in df:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)
    if "order_id" not in df:
        df["order_id"] = [f"order_{i}" for i in range(len(df))]
    if "order_quantity" not in df:
        df["order_quantity"] = 1.0
    if "order_amount" not in df:
        df["order_amount"] = 0.0
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["order_quantity"] = pd.to_numeric(df["order_quantity"], errors="coerce").fillna(0.0)
    df["order_amount"] = pd.to_numeric(df["order_amount"], errors="coerce").fillna(0.0)
    df = df.dropna(subset=["order_date", "manufacturer_code", "hospital_code", "drug_code"])
    df = df[(df["manufacturer_code"] != "") & (df["hospital_code"] != "") & (df["drug_code"] != "")]
    if cutoff_date:
        cutoff = pd.Timestamp(cutoff_date)
        if cutoff == cutoff.normalize():
            cutoff = cutoff + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
        df = df[df["order_date"] <= cutoff]
    profile = pd.DataFrame(
        [
            {"metric": "normalized_order_rows", "value": len(df)},
            {"metric": "manufacturer_count", "value": df["manufacturer_code"].nunique()},
            {"metric": "hospital_count", "value": df["hospital_code"].nunique()},
            {"metric": "drug_count", "value": df["drug_code"].nunique()},
        ]
    )
    return df.reset_index(drop=True), profile


def normalize_drug_master(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return pd.DataFrame(columns=["drug_code", "drug_name", "drug_category", "product_line_code", "product_line_name"])
    for col in ["drug_code", "drug_name", "drug_category", "product_line_code", "product_line_name"]:
        if col not in out:
            out[col] = ""
        out[col] = out[col].fillna("").astype(str)
    return out.drop_duplicates("drug_code")


def normalize_hospital_master(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return pd.DataFrame(columns=["hospital_code", "hospital_name", "region_code", "region_name", "hospital_level"])
    for col in ["hospital_code", "hospital_name", "region_code", "region_name", "hospital_level"]:
        if col not in out:
            out[col] = ""
        out[col] = out[col].fillna("").astype(str)
    return out.drop_duplicates("hospital_code")


def normalize_product_line_mapping(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return pd.DataFrame(columns=["drug_code", "product_line_code", "product_line_name"])
    for col in ["drug_code", "product_line_code", "product_line_name"]:
        if col not in out:
            out[col] = ""
        out[col] = out[col].fillna("").astype(str)
    return out.drop_duplicates("drug_code")


def normalize_delivery_events(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["delivery_date", "arrival_date"]:
        if col in out:
            out[col] = pd.to_datetime(out[col], errors="coerce")
    return out


def normalize_price_reference(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "reference_price" in out:
        out["reference_price"] = pd.to_numeric(out["reference_price"], errors="coerce")
    return out


def normalize_raw_tables(tables: dict[str, pd.DataFrame], cutoff_date: str) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    normalized: dict[str, pd.DataFrame] = {}
    normalized["orders"], order_profile = normalize_orders(tables["orders"], cutoff_date)
    normalized["drug_master"] = normalize_drug_master(tables.get("drug_master", pd.DataFrame()))
    normalized["hospital_master"] = normalize_hospital_master(tables.get("hospital_master", pd.DataFrame()))
    normalized["product_line_mapping"] = normalize_product_line_mapping(tables.get("product_line_mapping", pd.DataFrame()))
    normalized["delivery_events"] = normalize_delivery_events(tables.get("delivery_events", pd.DataFrame()))
    normalized["price_reference"] = normalize_price_reference(tables.get("price_reference", pd.DataFrame()))
    normalized["fact_entity_month"] = normalize_fact_entity_month(tables.get("fact_entity_month", pd.DataFrame()))
    normalized["entity_purchase_sequence"] = normalize_entity_purchase_sequence(tables.get("entity_purchase_sequence", pd.DataFrame()))
    return normalized, order_profile


def normalize_fact_entity_month(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out
    for col in ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source"]:
        if col in out:
            out[col] = out[col].fillna("").astype(str)
    if "purchase_month" in out:
        out["purchase_month"] = pd.to_datetime(out["purchase_month"], errors="coerce")
    if "last_purchase_time_in_month" in out:
        out["last_purchase_time_in_month"] = pd.to_datetime(out["last_purchase_time_in_month"], errors="coerce")
    return out


def normalize_entity_purchase_sequence(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out
    for col in ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source"]:
        if col in out:
            out[col] = out[col].fillna("").astype(str)
    for col in ["purchase_time", "previous_purchase_time"]:
        if col in out:
            out[col] = pd.to_datetime(out[col], errors="coerce")
    return out
