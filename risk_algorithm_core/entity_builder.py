"""Build monthly entity base from normalized orders."""

from __future__ import annotations

import pandas as pd


def build_monthly_entities(
    orders: pd.DataFrame,
    drug_master: pd.DataFrame,
    hospital_master: pd.DataFrame,
    product_line_mapping: pd.DataFrame,
    report_month: str,
    cutoff_date: str,
    horizons: list[str],
    use_product_line_group: bool = False,
) -> pd.DataFrame:
    if orders.empty:
        return pd.DataFrame()
    cutoff = pd.Timestamp(cutoff_date)
    df = orders[orders["order_date"] <= cutoff].copy()
    df["drug_group"] = df["drug_code"].astype(str)
    df["drug_group_source"] = "drug_code"

    if use_product_line_group and not product_line_mapping.empty:
        mapping = product_line_mapping[["drug_code", "product_line_code"]].drop_duplicates("drug_code")
        df = df.merge(mapping, on="drug_code", how="left")
        has_line = df["product_line_code"].fillna("").astype(str) != ""
        df.loc[has_line, "drug_group"] = df.loc[has_line, "product_line_code"].astype(str)
        df.loc[has_line, "drug_group_source"] = "product_line_mapping"

    group_cols = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source"]
    grouped = df.groupby(group_cols, dropna=False)
    base = grouped.agg(
        first_purchase_date=("order_date", "min"),
        last_purchase_date=("order_date", "max"),
        purchase_count_total=("order_id", "count"),
        purchase_quantity_total=("order_quantity", "sum"),
        order_amount_total=("order_amount", "sum"),
    ).reset_index()
    recent_start = cutoff - pd.DateOffset(months=3)
    recent = df[df["order_date"] > recent_start].groupby(group_cols).agg(
        purchase_count_recent=("order_id", "count"),
        purchase_quantity_recent=("order_quantity", "sum"),
        order_amount_recent=("order_amount", "sum"),
    ).reset_index()
    base = base.merge(recent, on=group_cols, how="left")
    for col in ["purchase_count_recent", "purchase_quantity_recent", "order_amount_recent"]:
        base[col] = base[col].fillna(0)
    base["cutoff_month"] = report_month
    base["cutoff_date"] = cutoff_date
    base["history_months"] = ((cutoff - base["first_purchase_date"]).dt.days / 30.4375).clip(lower=0).round(2)
    base["is_one_shot"] = base["purchase_count_total"] <= 1
    base["history_sufficiency_flag"] = base.apply(_history_flag, axis=1)

    base = _join_hospital(base, hospital_master)
    base = _join_drug(base, drug_master)
    base["entity_id"] = (
        base["manufacturer_code"].astype(str)
        + "|"
        + base["hospital_code"].astype(str)
        + "|"
        + base["drug_group"].astype(str)
    )
    expanded = base.loc[base.index.repeat(len(horizons))].copy()
    expanded["horizon"] = horizons * len(base)
    return expanded.reset_index(drop=True)


def _history_flag(row: pd.Series) -> str:
    if bool(row["is_one_shot"]) or float(row["history_months"]) < 3:
        return "history_insufficient"
    if float(row["history_months"]) < 12 or int(row["purchase_count_total"]) < 4:
        return "history_medium"
    return "history_sufficient"


def _join_hospital(base: pd.DataFrame, hospital_master: pd.DataFrame) -> pd.DataFrame:
    if hospital_master.empty:
        base["hospital_display_name"] = base["hospital_code"]
        base["region_code"] = ""
        base["region_display_name"] = ""
        base["hospital_level"] = ""
        return base
    cols = ["hospital_code", "hospital_name", "region_code", "region_name", "hospital_level"]
    out = base.merge(hospital_master[cols].drop_duplicates("hospital_code"), on="hospital_code", how="left")
    out["hospital_display_name"] = out["hospital_name"].fillna(out["hospital_code"])
    out["region_display_name"] = out["region_name"].fillna("")
    return out


def _join_drug(base: pd.DataFrame, drug_master: pd.DataFrame) -> pd.DataFrame:
    if drug_master.empty:
        base["drug_display_name"] = base["drug_group"]
        base["drug_category"] = ""
        base["product_line_code"] = ""
        base["product_line_display_name"] = ""
        return base
    cols = ["drug_code", "drug_name", "drug_category", "product_line_code", "product_line_name"]
    # Entity grain is still drug_group=drug_code by default; this join is for display and metadata.
    out = base.merge(drug_master[cols].drop_duplicates("drug_code"), left_on="drug_group", right_on="drug_code", how="left")
    out["drug_display_name"] = out["drug_name"].fillna(out["drug_group"])
    out["product_line_display_name"] = out["product_line_name"].fillna("")
    return out
