from __future__ import annotations

import pandas as pd

from app.adapters.base import DatasetBundle


def prepare_canonical_orders(bundle: DatasetBundle) -> pd.DataFrame:
    orders = bundle.orders.copy()
    if orders.empty:
        return orders

    orders["order_time"] = pd.to_datetime(orders["order_time"], errors="coerce")
    for numeric_field in [
        "purchase_qty",
        "purchase_amount",
        "purchase_price",
        "delivery_qty",
        "receipt_qty",
    ]:
        if numeric_field in orders.columns:
            orders[numeric_field] = pd.to_numeric(orders[numeric_field], errors="coerce")

    mapping = bundle.product_line_mapping.copy()
    if not mapping.empty and "drug_code" in mapping.columns:
        mapping_cols = [
            column
            for column in ["drug_code", "product_line_code", "product_line_name"]
            if column in mapping.columns
        ]
        orders = orders.merge(
            mapping[mapping_cols].drop_duplicates("drug_code"),
            on="drug_code",
            how="left",
        )

    drugs = bundle.drugs.copy()
    if not drugs.empty and "drug_code" in drugs.columns:
        metadata_cols = [
            column
            for column in ["drug_code", "drug_name", "spec", "dosage_form", "approval_no"]
            if column in drugs.columns and (column == "drug_code" or column not in orders.columns)
        ]
        if len(metadata_cols) > 1:
            orders = orders.merge(
                drugs[metadata_cols].drop_duplicates("drug_code"),
                on="drug_code",
                how="left",
            )

    if "product_line_code" not in orders.columns:
        orders["product_line_code"] = orders["drug_code"].astype(str)
    orders["product_line_code"] = orders["product_line_code"].fillna("UNKNOWN").astype(str)
    if "product_line_name" not in orders.columns:
        orders["product_line_name"] = orders["product_line_code"]
    orders["product_line_name"] = (
        orders["product_line_name"].fillna(orders["product_line_code"]).astype(str)
    )
    return orders
