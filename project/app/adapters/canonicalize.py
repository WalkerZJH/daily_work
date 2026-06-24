from __future__ import annotations

import pandas as pd

from app.adapters.base import DatasetBundle
from app.core.errors import DatasetLoadError

RAW_ORDER_COLUMN_MAP = {
    "数据唯一标识符": "source_row_id",
    "订单明细ID": "order_detail_id",
    "数据来源": "data_source",
    "订单名称": "order_name",
    "省": "province",
    "省编码": "province_code",
    "市": "city",
    "市编码": "city_code",
    "县区": "county",
    "县区编码": "county_code",
    "采购时间": "order_time",
    "药品编码": "drug_code",
    "药品医保编码": "insurance_drug_code",
    "通用名": "generic_name",
    "商品名": "trade_name",
    "剂型": "dosage_form",
    "规格": "spec",
    "转换系数": "conversion_factor",
    "采购单位": "purchase_unit",
    "材质": "material",
    "采购价(元)": "purchase_price",
    "采购数量": "purchase_qty",
    "采购金额(元)": "purchase_amount",
    "配送数量": "delivery_qty",
    "配送金额(元)": "delivery_amount",
    "到货数量": "receipt_qty",
    "到货金额(元)": "receipt_amount",
    "采购地址": "purchase_address",
    "订单状态": "order_status",
    "企业编码": "enterprise_code",
    "医疗机构等级": "org_level",
    "医疗机构详细等级": "org_level_detail",
    "医疗机构编码": "org_code",
    "医疗机构": "org_name",
    "配送企业编码": "distributor_code",
    "配送企业": "distributor_name",
    "生产企业编码": "manufacturer_code",
    "生产企业": "manufacturer_name",
    "药品类别": "drug_category",
    "数据更新时间": "updated_at",
    "配送时间": "delivery_time",
    "到货时间": "receipt_time",
    "项目名称": "project_name",
    "所有制形式": "ownership_type",
    "退回数量": "return_qty",
    "作废数量": "void_qty",
}

CANONICAL_ORDER_COLUMNS = [
    "source_row_id",
    "order_id",
    "order_detail_id",
    "data_source",
    "order_name",
    "province",
    "province_code",
    "city",
    "city_code",
    "county",
    "county_code",
    "order_time",
    "updated_at",
    "drug_code",
    "insurance_drug_code",
    "drug_name",
    "generic_name",
    "trade_name",
    "dosage_form",
    "spec",
    "conversion_factor",
    "purchase_unit",
    "purchase_price",
    "comparable_unit_price",
    "purchase_qty",
    "purchase_amount",
    "delivery_qty",
    "delivery_amount",
    "delivery_time",
    "receipt_qty",
    "receipt_amount",
    "receipt_time",
    "return_qty",
    "void_qty",
    "order_status",
    "enterprise_code",
    "org_code",
    "org_name",
    "org_level",
    "org_level_detail",
    "distributor_code",
    "distributor_name",
    "manufacturer_code",
    "manufacturer_name",
    "product_line_code",
    "product_line_name",
]

CRITICAL_CANONICAL_FIELDS = [
    "order_time",
    "drug_code",
    "org_code",
    "purchase_qty",
    "purchase_price",
]

NUMERIC_FIELDS = [
    "conversion_factor",
    "purchase_price",
    "purchase_qty",
    "purchase_amount",
    "delivery_qty",
    "delivery_amount",
    "receipt_qty",
    "receipt_amount",
    "return_qty",
    "void_qty",
]

DATETIME_FIELDS = ["order_time", "updated_at", "delivery_time", "receipt_time"]


def prepare_canonical_orders(bundle: DatasetBundle) -> pd.DataFrame:
    orders = canonicalize_order_dataframe(bundle.orders)
    if orders.empty:
        return orders

    mapping = bundle.product_line_mapping.copy()
    if not mapping.empty and "drug_code" in mapping.columns:
        mapping_cols = [column for column in ["drug_code"] if column in mapping.columns]
        rename_map: dict[str, str] = {}
        for column in ["product_line_code", "product_line_name"]:
            if column in mapping.columns:
                mapping_cols.append(column)
                rename_map[column] = f"{column}_mapped"
        orders = orders.merge(
            mapping[mapping_cols].drop_duplicates("drug_code").rename(columns=rename_map),
            on="drug_code",
            how="left",
        )
        for column in ["product_line_code", "product_line_name"]:
            mapped_column = f"{column}_mapped"
            if mapped_column in orders.columns:
                orders[column] = orders[mapped_column].combine_first(_series_or_na(orders, column))
                orders = orders.drop(columns=[mapped_column])

    drugs = bundle.drugs.copy()
    if not drugs.empty and "drug_code" in drugs.columns:
        metadata_cols = [column for column in ["drug_code"] if column in drugs.columns]
        rename_map = {}
        for column in ["drug_name", "spec", "dosage_form", "approval_no"]:
            if column in drugs.columns:
                metadata_cols.append(column)
                rename_map[column] = f"{column}_dim"
        if len(metadata_cols) > 1:
            orders = orders.merge(
                drugs[metadata_cols].drop_duplicates("drug_code").rename(columns=rename_map),
                on="drug_code",
                how="left",
            )
            for column in ["drug_name", "spec", "dosage_form", "approval_no"]:
                dim_column = f"{column}_dim"
                if dim_column in orders.columns:
                    orders[column] = orders[dim_column].combine_first(_series_or_na(orders, column))
                    orders = orders.drop(columns=[dim_column])

    if "product_line_code" not in orders.columns:
        orders["product_line_code"] = orders["drug_code"].astype(str)
    orders["product_line_code"] = orders["product_line_code"].fillna(
        _first_non_empty(orders, ["generic_name", "insurance_drug_code", "drug_code"])
    )
    orders["product_line_code"] = orders["product_line_code"].fillna("UNKNOWN").astype(str)
    if "product_line_name" not in orders.columns:
        orders["product_line_name"] = _first_non_empty(
            orders, ["generic_name", "trade_name", "drug_code"]
        )
    orders["product_line_name"] = (
        orders["product_line_name"].fillna(orders["product_line_code"]).astype(str)
    )
    return orders


def canonicalize_order_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    orders = frame.rename(columns=RAW_ORDER_COLUMN_MAP).copy()
    missing = [field for field in CRITICAL_CANONICAL_FIELDS if field not in orders.columns]
    if missing:
        raise DatasetLoadError(f"Missing critical canonical order fields: {', '.join(missing)}")

    if "order_id" not in orders.columns:
        if "order_detail_id" in orders.columns:
            orders["order_id"] = orders["order_detail_id"]
        elif "source_row_id" in orders.columns:
            orders["order_id"] = orders["source_row_id"]
        else:
            orders["order_id"] = orders.index.astype(str)
    if "order_detail_id" not in orders.columns:
        orders["order_detail_id"] = orders["order_id"]
    if "source_row_id" not in orders.columns:
        orders["source_row_id"] = orders["order_id"]

    for field in DATETIME_FIELDS:
        if field in orders.columns:
            orders[field] = pd.to_datetime(orders[field], errors="coerce")
    for field in NUMERIC_FIELDS:
        if field in orders.columns:
            orders[field] = pd.to_numeric(orders[field], errors="coerce")

    if "drug_name" not in orders.columns:
        orders["drug_name"] = _first_non_empty(orders, ["generic_name", "trade_name", "drug_code"])
    if "product_line_code" not in orders.columns:
        orders["product_line_code"] = _first_non_empty(
            orders, ["generic_name", "insurance_drug_code", "drug_code"]
        )
    if "product_line_name" not in orders.columns:
        orders["product_line_name"] = _first_non_empty(
            orders, ["generic_name", "trade_name", "drug_code"]
        )

    # v1 fallback only: business must confirm whether purchase_price / conversion_factor
    # is the correct comparable unit price for every procurement unit.
    if "conversion_factor" not in orders.columns:
        orders["conversion_factor"] = pd.NA
    orders["conversion_factor"] = pd.to_numeric(orders["conversion_factor"], errors="coerce")
    invalid_factor = orders["conversion_factor"].isna() | (orders["conversion_factor"] <= 0)
    orders["comparable_unit_price"] = pd.to_numeric(orders["purchase_price"], errors="coerce")
    valid_factor = ~invalid_factor
    if valid_factor.any():
        orders.loc[valid_factor, "comparable_unit_price"] = (
            orders.loc[valid_factor, "purchase_price"] / orders.loc[valid_factor, "conversion_factor"]
        )
    warnings = [[] for _ in range(len(orders))]
    for idx in orders.index[invalid_factor]:
        pos = orders.index.get_loc(idx)
        warnings[pos].append("INVALID_CONVERSION_FACTOR")
    orders["canonical_warnings"] = warnings

    for column in CANONICAL_ORDER_COLUMNS:
        if column not in orders.columns:
            orders[column] = pd.NA
    return orders


def derive_drugs_from_orders(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return pd.DataFrame(
            columns=[
                "drug_code",
                "insurance_drug_code",
                "generic_name",
                "trade_name",
                "drug_name",
                "spec",
                "dosage_form",
                "manufacturer_code",
                "manufacturer_name",
                "drug_category",
            ]
        )
    columns = [
        "drug_code",
        "insurance_drug_code",
        "generic_name",
        "trade_name",
        "drug_name",
        "spec",
        "dosage_form",
        "manufacturer_code",
        "manufacturer_name",
        "drug_category",
    ]
    return orders[[column for column in columns if column in orders.columns]].drop_duplicates("drug_code")


def derive_orgs_from_orders(orders: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "org_code",
        "org_name",
        "org_level",
        "org_level_detail",
        "province",
        "province_code",
        "city",
        "city_code",
        "county",
        "county_code",
    ]
    if orders.empty:
        return pd.DataFrame(columns=columns)
    return orders[[column for column in columns if column in orders.columns]].drop_duplicates("org_code")


def derive_product_line_mapping_from_orders(orders: pd.DataFrame) -> pd.DataFrame:
    columns = ["drug_code", "product_line_code", "product_line_name"]
    if orders.empty:
        return pd.DataFrame(columns=[*columns, "mapping_rule", "confidence"])
    mapping = orders[[column for column in columns if column in orders.columns]].drop_duplicates("drug_code")
    mapping["mapping_rule"] = "fallback_from_order_wide_table"
    mapping["confidence"] = 0.5
    return mapping


def _first_non_empty(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    result = pd.Series(pd.NA, index=frame.index, dtype="object")
    for column in columns:
        if column not in frame.columns:
            continue
        values = frame[column]
        mask = result.isna() | (result.astype(str).str.strip() == "")
        result.loc[mask] = values.loc[mask]
    return result


def _series_or_na(frame: pd.DataFrame, column: str) -> pd.Series:
    if column in frame.columns:
        return frame[column]
    return pd.Series(pd.NA, index=frame.index, dtype="object")
