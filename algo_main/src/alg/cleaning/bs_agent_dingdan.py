"""Internal helpers for the BS_Agent_DingDan v2 cleaning pipeline.

The production and notebook entry point is
``alg.cleaning.bs_agent_dingdan_pipeline.run_bs_agent_dingdan_cleaning_pipeline``.
Keep this module as implementation support and backward-compatible helper
surface; do not use it as a separate main cleaning workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


@dataclass(frozen=True)
class CleaningPaths:
    project_root: Path
    config_path: Path
    status_map_path: Path
    hospital_level_map_path: Path
    export_eda: Path
    export_clean: Path
    export_mappings: Path
    raw_parquet_path: Path
    clean_parquet_path: Path
    sample_csv_path: Path


def build_paths(project_root: Path | None = None) -> CleaningPaths:
    root = (project_root or Path.cwd()).resolve()
    if root.name == "notebooks":
        root = root.parent
    return CleaningPaths(
        project_root=root,
        config_path=root / "configs/data_schema/bs_agent_dingdan_schema.yaml",
        status_map_path=root / "configs/mappings/order_status_map.yaml",
        hospital_level_map_path=root / "configs/mappings/hospital_grade_map.yaml",
        export_eda=root / "exports/eda",
        export_clean=root / "exports/clean",
        export_mappings=root / "exports/mappings",
        raw_parquet_path=root / "data/01_raw/BS_Agent_DingDan.parquet",
        clean_parquet_path=root / "data/03_cleaned/bs_agent_dingdan_clean.parquet",
        sample_csv_path=root / "exports/raw/BS_Agent_DingDan_sample.csv",
    )


def ensure_output_dirs(paths: CleaningPaths) -> None:
    for path in [
        paths.export_eda,
        paths.export_clean,
        paths.export_mappings,
        paths.raw_parquet_path.parent,
        paths.clean_parquet_path.parent,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_env(project_root: Path) -> tuple[str | None, str]:
    """Load SQL settings without printing secrets."""

    import os

    load_dotenv(project_root / ".env")
    return os.getenv("SQL_DATABASE_URL"), os.getenv("SQL_TABLE", "BS_Agent_DingDan")


def build_column_maps(schema: dict[str, Any]) -> tuple[dict[str, str], dict[str, str], list[str]]:
    raw_to_alias = {column["raw_name"]: column["alias"] for column in schema["columns"]}
    alias_to_raw = {alias: raw for raw, alias in raw_to_alias.items()}
    return raw_to_alias, alias_to_raw, list(raw_to_alias)


def quote_sqlserver_identifier(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


def projected_columns_sql(columns: list[str]) -> str:
    return ", ".join(quote_sqlserver_identifier(column) for column in columns)


def read_sql_sample(
    sql_database_url: str | None,
    sql_table: str,
    raw_columns: list[str],
    max_rows: int,
) -> pd.DataFrame:
    if not sql_database_url:
        raise RuntimeError('SQL_DATABASE_URL is not configured. Use mode="parquet" or provide .env.')
    engine = create_engine(sql_database_url)
    sql = (
        f"SELECT TOP ({int(max_rows)}) {projected_columns_sql(raw_columns)} "
        f"FROM {quote_sqlserver_identifier(sql_table)}"
    )
    return pd.read_sql(text(sql), engine)


def export_sql_full_to_parquet(
    sql_database_url: str | None,
    sql_table: str,
    raw_columns: list[str],
    output_path: Path,
    chunksize: int,
) -> Path:
    if not sql_database_url:
        raise RuntimeError("SQL_DATABASE_URL is not configured.")
    import pyarrow as pa
    import pyarrow.parquet as pq

    engine = create_engine(sql_database_url)
    sql = f"SELECT {projected_columns_sql(raw_columns)} FROM {quote_sqlserver_identifier(sql_table)}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = None
    total = 0
    try:
        for chunk in pd.read_sql(text(sql), engine, chunksize=chunksize):
            table = pa.Table.from_pandas(chunk, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(output_path, table.schema)
            writer.write_table(table)
            total += len(chunk)
            print(f"wrote rows={total}")
    finally:
        if writer is not None:
            writer.close()
    return output_path


def load_input_dataframe(
    mode: str,
    paths: CleaningPaths,
    sql_database_url: str | None,
    sql_table: str,
    raw_columns: list[str],
    max_rows: int | None,
    chunksize: int,
    use_cache: bool = True,
    refresh_cache: bool = False,
) -> pd.DataFrame:
    """
    Load BS_Agent_DingDan input data.

    Cache policy:
    - If use_cache=True and refresh_cache=False and raw_parquet_path exists,
      read raw_parquet_path directly for parquet/sql_full_to_parquet modes.
    - sql_full_to_parquet exports SQL to raw_parquet_path only when cache is absent
      or refresh_cache=True.
    - sql_sample uses sample_csv_path cache for sample data.
    """

    raw_parquet_path = Path(paths.raw_parquet_path)
    sample_csv_path = Path(paths.sample_csv_path)

    if mode not in {"parquet", "sql_full_to_parquet", "sql_sample"}:
        raise ValueError(f"Unsupported mode: {mode}")

    # 1. Explicit parquet mode: must read local parquet.
    if mode == "parquet":
        if not raw_parquet_path.exists():
            raise FileNotFoundError(
                f"Parquet cache not found: {raw_parquet_path}. "
                "Use mode='sql_full_to_parquet' to create it first."
            )
        return pd.read_parquet(raw_parquet_path)

    # 2. Full SQL mode: prefer existing parquet cache unless refresh is requested.
    if mode == "sql_full_to_parquet":
        if use_cache and not refresh_cache and raw_parquet_path.exists():
            return pd.read_parquet(raw_parquet_path)

        if not sql_database_url:
            raise ValueError("sql_database_url is required for sql_full_to_parquet mode.")

        export_sql_full_to_parquet(
            sql_database_url=sql_database_url,
            sql_table=sql_table,
            raw_columns=raw_columns,
            output_path=raw_parquet_path,
            chunksize=chunksize,
        )
        return pd.read_parquet(raw_parquet_path)

    # 3. Sample SQL mode: sample cache is separate from full raw parquet cache.
    if mode == "sql_sample":
        if use_cache and not refresh_cache and sample_csv_path.exists():
            return pd.read_csv(sample_csv_path)

        if not sql_database_url:
            raise ValueError("sql_database_url is required for sql_sample mode.")

        df = read_sql_sample(sql_database_url, sql_table, raw_columns, max_rows)

        # Optional: cache sample for reproducible review.
        if use_cache:
            sample_csv_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(sample_csv_path, index=False, encoding="utf-8-sig")

        return df

    raise ValueError(f"Unsupported mode: {mode}")

def normalize_code(series: pd.Series) -> pd.Series:
    return series.astype("string").str.replace(r"\.0$", "", regex=True).str.strip()


def top_values(df: pd.DataFrame, column: str, n: int = 20) -> pd.DataFrame:
    if column not in df.columns:
        return pd.DataFrame(columns=["value", "count"])
    return (
        df[column]
        .astype("string")
        .value_counts(dropna=False)
        .head(n)
        .rename_axis("value")
        .reset_index(name="count")
    )


def field_profile(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in df.columns:
        rows.append(
            {
                "column": column,
                "null_count": int(df[column].isna().sum()),
                "null_rate": float(df[column].isna().mean()),
                "distinct_count": int(df[column].nunique(dropna=True)),
            }
        )
    return pd.DataFrame(rows).sort_values(["null_rate", "column"])


def save_basic_profile(
    df: pd.DataFrame, alias_to_raw: dict[str, str], export_eda: Path
) -> tuple[dict[str, Any], pd.DataFrame]:
    purchase_col = alias_to_raw["purchase_time"]
    purchase_time = (
        pd.to_datetime(df.get(purchase_col), errors="coerce")
        if purchase_col in df.columns
        else pd.Series(dtype="datetime64[ns]")
    )
    summary = {
        "row_count": len(df),
        "column_count": df.shape[1],
        "purchase_time_min": str(purchase_time.min()) if len(purchase_time) else None,
        "purchase_time_max": str(purchase_time.max()) if len(purchase_time) else None,
    }
    profile = field_profile(df)
    profile.to_csv(export_eda / "field_distinct_counts.csv", index=False, encoding="utf-8-sig")
    return summary, profile


def analyze_identifiers(
    df: pd.DataFrame, alias_to_raw: dict[str, str], export_eda: Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    row_uid_col = alias_to_raw["row_uid"]
    detail_col = alias_to_raw["order_detail_id"]
    sample_cols = [
        alias_to_raw[key]
        for key in [
            "order_detail_id",
            "row_uid",
            "order_status_raw",
            "updated_at",
            "distributor_name",
            "raw_sensitive_purchase_quantity",
            "raw_sensitive_delivery_quantity",
            "raw_sensitive_arrival_quantity",
        ]
        if alias_to_raw[key] in df.columns
    ]
    report = pd.DataFrame(
        [
            {"check": "row_uid_unique", "value": bool(df[row_uid_col].is_unique) if row_uid_col in df else None},
            {
                "check": "order_detail_id_unique",
                "value": bool(df[detail_col].is_unique) if detail_col in df else None,
            },
            {
                "check": "row_uid_distinct",
                "value": int(df[row_uid_col].nunique(dropna=True)) if row_uid_col in df else None,
            },
            {
                "check": "order_detail_id_distinct",
                "value": int(df[detail_col].nunique(dropna=True)) if detail_col in df else None,
            },
        ]
    )
    report.to_csv(export_eda / "id_duplicate_report.csv", index=False, encoding="utf-8-sig")
    samples = pd.DataFrame()
    if detail_col in df.columns:
        dup_ids = df[df[detail_col].duplicated(keep=False)][detail_col].dropna().head(50)
        samples = df[df[detail_col].isin(dup_ids)][sample_cols].sort_values(detail_col)
    samples.to_csv(
        export_eda / "order_detail_duplicate_samples.csv", index=False, encoding="utf-8-sig"
    )
    return report, samples


def save_source_order_profiles(
    df: pd.DataFrame, alias_to_raw: dict[str, str], export_eda: Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    source_top = top_values(df, alias_to_raw["data_source"])
    order_name_top = top_values(df, alias_to_raw["order_name"])
    source_top.to_csv(export_eda / "data_source_value_counts.csv", index=False, encoding="utf-8-sig")
    order_name_top.to_csv(
        export_eda / "order_name_value_counts.csv", index=False, encoding="utf-8-sig"
    )
    return source_top, order_name_top


def build_region_mapping(
    df: pd.DataFrame, alias_to_raw: dict[str, str], export_eda: Path, export_mappings: Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    county_raw = alias_to_raw["county_code"]
    region = pd.DataFrame()
    if county_raw in df.columns:
        county_code = normalize_code(df[county_raw]).str.zfill(6)
        region = pd.DataFrame(
            {
                "province_code": county_code.str.slice(0, 2) + "0000",
                "province_name": df.get(alias_to_raw["province_name"]),
                "city_code": county_code.str.slice(0, 4) + "00",
                "city_name": df.get(alias_to_raw["city_name"]),
                "county_code": county_code,
                "county_name": df.get(alias_to_raw["county_name"]),
            }
        ).drop_duplicates()
    region.to_csv(export_mappings / "region_code_map.csv", index=False, encoding="utf-8-sig")
    conflicts = []
    for code_col, name_col in [
        ("province_code", "province_name"),
        ("city_code", "city_name"),
        ("county_code", "county_name"),
    ]:
        if not region.empty:
            tmp = (
                region.groupby(code_col)[name_col]
                .nunique(dropna=True)
                .reset_index(name="name_distinct_count")
            )
            tmp = tmp[tmp["name_distinct_count"] > 1]
            tmp["check"] = f"{code_col}_to_{name_col}"
            conflicts.append(tmp)
    conflict_df = pd.concat(conflicts, ignore_index=True) if conflicts else pd.DataFrame()
    conflict_df.to_csv(export_eda / "region_code_conflicts.csv", index=False, encoding="utf-8-sig")
    return region, conflict_df


def analyze_drug_code_consistency(
    df: pd.DataFrame, alias_to_raw: dict[str, str], export_eda: Path
) -> pd.DataFrame:
    drug_col = alias_to_raw["drug_code"]
    insurance_col = alias_to_raw["insurance_drug_code"]
    rows = []
    if drug_col in df.columns and insurance_col in df.columns:
        drug = normalize_code(df[drug_col])
        insurance = normalize_code(df[insurance_col])
        comparable = drug.notna() & insurance.notna()
        rows.append({"metric": "comparable_rows", "value": int(comparable.sum())})
        rows.append(
            {
                "metric": "equal_ratio",
                "value": float((drug[comparable] == insurance[comparable]).mean())
                if comparable.any()
                else np.nan,
            }
        )
        one_to_one = (
            df[[drug_col, insurance_col]]
            .dropna()
            .drop_duplicates()
            .groupby(drug_col)[insurance_col]
            .nunique()
            .reset_index(name="insurance_distinct_count")
        )
        rows.append(
            {
                "metric": "drug_code_multi_insurance_count",
                "value": int((one_to_one["insurance_distinct_count"] > 1).sum()),
            }
        )
    report = pd.DataFrame(rows)
    report.to_csv(
        export_eda / "drug_code_vs_insurance_code_report.csv", index=False, encoding="utf-8-sig"
    )
    return report


def analyze_numeric_desensitization(
    df: pd.DataFrame, alias_to_raw: dict[str, str], export_eda: Path
) -> pd.DataFrame:
    """Check same-type numeric ratios under the updated desensitization policy."""

    numeric_aliases = [
        "raw_sensitive_purchase_price",
        "raw_sensitive_purchase_quantity",
        "raw_sensitive_purchase_amount",
        "raw_sensitive_delivery_quantity",
        "raw_sensitive_delivery_amount",
        "raw_sensitive_arrival_quantity",
        "raw_sensitive_arrival_amount",
    ]
    numeric_report: list[dict[str, Any]] = []
    numeric_df = pd.DataFrame(index=df.index)
    for alias in numeric_aliases:
        raw = alias_to_raw[alias]
        if raw in df.columns:
            series = pd.to_numeric(df[raw], errors="coerce")
            numeric_df[alias] = series
            numeric_report.append(
                {
                    "metric_group": "field_distribution",
                    "field": alias,
                    "description": "null/negative/zero/distribution summary",
                    "null_rate": float(series.isna().mean()),
                    "negative_rate": float((series < 0).mean()),
                    "zero_rate": float((series == 0).mean()),
                    "min": series.min(),
                    "p50": series.quantile(0.5),
                    "p95": series.quantile(0.95),
                    "max": series.max(),
                }
            )
    ratio_specs = [
        (
            "quantity_ratio_preserved",
            "raw_sensitive_delivery_quantity",
            "raw_sensitive_purchase_quantity",
            "delivery_rate",
        ),
        (
            "quantity_ratio_preserved",
            "raw_sensitive_arrival_quantity",
            "raw_sensitive_delivery_quantity",
            "arrival_rate",
        ),
        (
            "quantity_ratio_preserved",
            "raw_sensitive_arrival_quantity",
            "raw_sensitive_purchase_quantity",
            "overall_arrival_rate",
        ),
        (
            "amount_ratio_preserved",
            "raw_sensitive_delivery_amount",
            "raw_sensitive_purchase_amount",
            "delivery_amount_to_purchase_amount_ratio",
        ),
        (
            "amount_ratio_preserved",
            "raw_sensitive_arrival_amount",
            "raw_sensitive_delivery_amount",
            "arrival_amount_to_delivery_amount_ratio",
        ),
        (
            "amount_ratio_preserved",
            "raw_sensitive_arrival_amount",
            "raw_sensitive_purchase_amount",
            "arrival_amount_to_purchase_amount_ratio",
        ),
    ]
    for group, numerator, denominator, metric in ratio_specs:
        if {numerator, denominator}.issubset(numeric_df.columns):
            ratio = numeric_df[numerator] / numeric_df[denominator].replace(0, np.nan)
            numeric_report.append(
                {
                    "metric_group": group,
                    "field": metric,
                    "description": f"{numerator} / {denominator}",
                    "null_rate": float(ratio.isna().mean()),
                    "negative_rate": float((ratio < 0).mean()),
                    "zero_rate": float((ratio == 0).mean()),
                    "min": ratio.min(),
                    "p50": ratio.quantile(0.5),
                    "p95": ratio.quantile(0.95),
                    "max": ratio.max(),
                }
            )
    policy_notes = pd.DataFrame(
        [
            {
                "metric_group": "policy",
                "field": "price_from_amount_quantity",
                "description": "FORBIDDEN: do not infer real unit price from purchase_amount / purchase_quantity because amount and quantity use different multipliers m/q.",
            },
            {
                "metric_group": "policy",
                "field": "purchase_price_consistency",
                "description": "FORBIDDEN: do not validate purchase_price against purchase_amount / purchase_quantity because purchase_price may be independently desensitized.",
            },
            {
                "metric_group": "policy",
                "field": "trend_usage",
                "description": "ALLOWED: quantity trends, amount trends, order frequency trends, and same-type field ratios.",
            },
        ]
    )
    report = pd.concat([pd.DataFrame(numeric_report), policy_notes], ignore_index=True)
    report.to_csv(export_eda / "numeric_desensitization_report.csv", index=False, encoding="utf-8-sig")
    return report


def _keyword_match(value: Any, rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    text_value = "" if pd.isna(value) else str(value).strip()
    for rule in rules:
        if any(keyword in text_value for keyword in rule.get("keywords", [])):
            return rule
    return None


def map_status_value(value: Any, status_map: dict[str, Any]) -> pd.Series:
    rule = _keyword_match(value, status_map["rules"])
    if rule:
        return pd.Series({"order_status_stage": rule["stage"], "order_status_code": rule["code"]})
    default = status_map["default"]
    return pd.Series({"order_status_stage": default["stage"], "order_status_code": default["code"]})


STATUS_LIFECYCLE_GROUPS: list[dict[str, Any]] = [
    {
        "keywords": ["已收货", "已入库", "到货确认", "到货", "入库", "全部收货", "医院已入库", "全部收货确认", "医院已收货", "确认收货", "配送完成"],
        "order_phase_code": 60,
        "order_phase_label": "received",
        "delivery_state_code": 5,
        "delivery_state_label": "received",
        "order_terminal_flag": 1,
        "order_failure_flag": 0,
        "needs_manual_review": False,
    },
    {
        "keywords": ["全部发货", "已发货", "已配送", "已配送待收货", "已出库", "经销商配送", "已提交已配送", "企业已配送", "已发出", "配送企业已配送"],
        "order_phase_code": 50,
        "order_phase_label": "dispatched",
        "delivery_state_code": 3,
        "delivery_state_label": "dispatched_not_received",
        "order_terminal_flag": 0,
        "order_failure_flag": 0,
        "needs_manual_review": False,
    },
    {
        "keywords": ["部分发货", "部分配送"],
        "order_phase_code": 50,
        "order_phase_label": "dispatched",
        "delivery_state_code": 4,
        "delivery_state_label": "partially_dispatched",
        "order_terminal_flag": 0,
        "order_failure_flag": 0,
        "needs_manual_review": False,
    },
    {
        "keywords": ["已确认", "已响应", "配送企业已确认", "投标企业确认"],
        "order_phase_code": 30,
        "order_phase_label": "confirmed",
        "delivery_state_code": 2,
        "delivery_state_label": "confirmed_not_dispatched",
        "order_terminal_flag": 0,
        "order_failure_flag": 0,
        "needs_manual_review": False,
    },
    {
        "keywords": ["确认配送", "企业确认配送", "待发货", "未确认送货", "已提交待配送", "已提交配送", "提交配送", "已确认待配送"],
        "order_phase_code": 40,
        "order_phase_label": "pending_dispatch",
        "delivery_state_code": 2,
        "delivery_state_label": "confirmed_not_dispatched",
        "order_terminal_flag": 0,
        "order_failure_flag": 0,
        "needs_manual_review": False,
    },
    {
        "keywords": ["已提交", "医院已提交", "未确认", "未及时确认", "待响应", "已提交待确认", "待确认", "已下发网采证明"],
        "order_phase_code": 20,
        "order_phase_label": "submitted_or_pending",
        "delivery_state_code": 1,
        "delivery_state_label": "ordered_not_confirmed",
        "order_terminal_flag": 0,
        "order_failure_flag": 0,
        "needs_manual_review": False,
    },
    {
        "keywords": ["正式计划", "未提交"],
        "order_phase_code": 10,
        "order_phase_label": "draft_or_plan",
        "delivery_state_code": 1,
        "delivery_state_label": "ordered_not_confirmed",
        "order_terminal_flag": 0,
        "order_failure_flag": 0,
        "needs_manual_review": False,
    },
    {
        "keywords": ["已开全部发票", "结算完毕", "已付款"],
        "order_phase_code": 70,
        "order_phase_label": "invoiced_or_paid",
        "delivery_state_code": 6,
        "delivery_state_label": "completed_or_settled",
        "order_terminal_flag": 1,
        "order_failure_flag": 0,
        "needs_manual_review": False,
    },
    {
        "keywords": ["成交完成", "已完成"],
        "order_phase_code": 80,
        "order_phase_label": "completed",
        "delivery_state_code": 6,
        "delivery_state_label": "completed_or_settled",
        "order_terminal_flag": 1,
        "order_failure_flag": 0,
        "needs_manual_review": False,
    },
    {
        "keywords": ["退货完成", "拒绝收货", "拒收", "退货"],
        "order_phase_code": 90,
        "order_phase_label": "returned_or_rejected",
        "delivery_state_code": 7,
        "delivery_state_label": "returned_or_rejected_receipt",
        "order_terminal_flag": 1,
        "order_failure_flag": 1,
        "needs_manual_review": False,
    },
    {
        "keywords": ["无法配送", "拒绝配送", "企业拒绝配送", "缺货", "未及时配送", "拒绝响应", "拒绝确认"],
        "order_phase_code": 100,
        "order_phase_label": "cancelled_or_failed",
        "delivery_state_code": 9,
        "delivery_state_label": "delivery_failed",
        "order_terminal_flag": 1,
        "order_failure_flag": 1,
        "needs_manual_review": False,
    },
    {
        "keywords": ["撤废", "撤销", "未发货作废", "已撤废", "已撤销", "7天未阅读作废", "撤单", "已撤单", "已作废", "订单到期", "取消采购", "作废", "逾期作废", "失效", "自主撤单"],
        "order_phase_code": 100,
        "order_phase_label": "cancelled_or_failed",
        "delivery_state_code": 8,
        "delivery_state_label": "cancelled_or_voided",
        "order_terminal_flag": 1,
        "order_failure_flag": 1,
        "needs_manual_review": False,
    },
    {
        "keywords": ["未作废"],
        "order_phase_code": 0,
        "order_phase_label": "unknown",
        "delivery_state_code": 0,
        "delivery_state_label": "unknown",
        "order_terminal_flag": -1,
        "order_failure_flag": -1,
        "needs_manual_review": True,
    },
]


def order_status_lifecycle_map_dataframe() -> pd.DataFrame:
    rows = []
    for group in STATUS_LIFECYCLE_GROUPS:
        for keyword in group["keywords"]:
            row = {k: v for k, v in group.items() if k != "keywords"}
            row["order_status_norm"] = keyword
            rows.append(row)
    mapping = pd.DataFrame(rows)
    columns = [
        "order_status_norm",
        "order_phase_code",
        "order_phase_label",
        "delivery_state_code",
        "delivery_state_label",
        "order_terminal_flag",
        "order_failure_flag",
        "needs_manual_review",
    ]
    mapping = mapping[columns].sort_values("order_status_norm")
    return mapping


def build_order_status_lifecycle_map(export_mappings: Path) -> pd.DataFrame:
    mapping = order_status_lifecycle_map_dataframe()
    mapping.to_csv(export_mappings / "order_status_lifecycle_map.csv", index=False, encoding="utf-8-sig")
    return mapping


def normalize_status_text(value: Any) -> str:
    return "" if pd.isna(value) else str(value).strip()


def map_status_lifecycle_value(value: Any, lifecycle_map: pd.DataFrame) -> pd.Series:
    text_value = normalize_status_text(value)
    if text_value == "":
        return pd.Series(
            {
                "order_status_norm": "",
                "order_phase_code": 0,
                "order_phase_label": "unknown",
                "delivery_state_code": 0,
                "delivery_state_label": "unknown",
                "order_terminal_flag": -1,
                "order_failure_flag": -1,
                "needs_manual_review": True,
            }
        )
    exact = lifecycle_map[lifecycle_map["order_status_norm"] == text_value]
    if not exact.empty:
        return exact.iloc[0]
    for _, row in lifecycle_map.iterrows():
        if row["order_status_norm"] and row["order_status_norm"] in text_value:
            out = row.copy()
            out["order_status_norm"] = text_value
            return out
    return pd.Series(
        {
            "order_status_norm": text_value,
            "order_phase_code": 0,
            "order_phase_label": "unknown",
            "delivery_state_code": 0,
            "delivery_state_label": "unknown",
            "order_terminal_flag": -1,
            "order_failure_flag": -1,
            "needs_manual_review": True,
        }
    )


def apply_order_status_lifecycle(
    df: pd.DataFrame, export_eda: Path, export_mappings: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lifecycle_map = build_order_status_lifecycle_map(export_mappings)
    mapped = df.get("order_status_raw", pd.Series(index=df.index, dtype="object")).apply(
        lambda value: map_status_lifecycle_value(value, lifecycle_map)
    )
    out = df.copy()
    for column in mapped.columns:
        out[column] = mapped[column].values
    coverage = build_order_status_mapping_coverage(out)
    coverage.to_csv(export_eda / "order_status_mapping_coverage.csv", index=False, encoding="utf-8-sig")
    suspicious = build_order_status_suspicious_mapping(out)
    suspicious.to_csv(
        export_eda / "order_status_suspicious_mapping.csv", index=False, encoding="utf-8-sig"
    )
    return out, coverage, suspicious


def build_order_status_mapping_coverage(df: pd.DataFrame) -> pd.DataFrame:
    total_rows = len(df)
    mapped_rows = int((df["order_phase_code"] != 0).sum()) if "order_phase_code" in df else 0
    rows: list[dict[str, Any]] = [
        {"metric_group": "summary", "metric": "total_rows", "value": total_rows},
        {"metric_group": "summary", "metric": "mapped_rows", "value": mapped_rows},
        {"metric_group": "summary", "metric": "unmapped_rows", "value": total_rows - mapped_rows},
        {
            "metric_group": "summary",
            "metric": "mapping_coverage",
            "value": mapped_rows / total_rows if total_rows else np.nan,
        },
    ]
    for column in ["order_phase_code", "delivery_state_code", "order_terminal_flag", "order_failure_flag"]:
        if column in df:
            for value, count in df[column].value_counts(dropna=False).sort_index().items():
                rows.append({"metric_group": column, "metric": value, "value": int(count)})
    return pd.DataFrame(rows)


def build_order_status_suspicious_mapping(df: pd.DataFrame) -> pd.DataFrame:
    if "order_status_raw" not in df:
        return pd.DataFrame()
    status = df["order_status_raw"].astype("string").fillna("")
    failure_or_unknown_expected = status.str.contains("无法配送|拒绝配送|企业拒绝配送|拒绝响应|拒绝确认|缺货|未及时配送|未作废", regex=True)
    checks = [
        (
            status.str.contains("收货|入库|到货", regex=True)
            & ~status.str.contains("拒绝收货|拒收|待收货", regex=True)
            & (df["delivery_state_code"] != 5),
            "receive_keyword_not_received_state",
        ),
        (
            status.str.contains("拒绝|无法|缺货|作废|撤销|撤单|失效|退货|拒收", regex=True)
            & ~status.str.contains("未作废", regex=True)
            & (df["order_failure_flag"] != 1),
            "failure_keyword_not_failure_flag",
        ),
        (
            status.str.contains("未确认|待确认", regex=True)
            & ~status.str.contains("未确认送货", regex=True)
            & (df["order_phase_code"] >= 30),
            "pending_confirm_keyword_late_phase",
        ),
        (
            status.str.contains("全部发货|已发货|已配送|部分配送|部分发货|已出库|出库", regex=True)
            & ~status.str.contains("待发货|未发货", regex=True)
            & ~failure_or_unknown_expected
            & (~df["delivery_state_code"].isin([3, 4])),
            "dispatch_keyword_not_dispatch_state",
        ),
        ((status == "") & (~df["needs_manual_review"].astype(bool)), "empty_status_not_manual_review"),
    ]
    frames = []
    cols = [
        column
        for column in [
            "row_uid",
            "order_detail_id",
            "order_status_raw",
            "order_phase_code",
            "delivery_state_code",
            "order_terminal_flag",
            "order_failure_flag",
            "needs_manual_review",
        ]
        if column in df.columns
    ]
    for mask, reason in checks:
        tmp = df.loc[mask, cols].copy()
        tmp["suspicious_reason"] = reason
        tmp["suspicious_level"] = "hard"
        frames.append(tmp)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols + ["suspicious_reason"])


def analyze_status(
    df: pd.DataFrame,
    alias_to_raw: dict[str, str],
    status_map: dict[str, Any],
    export_eda: Path,
    export_mappings: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    status_col = alias_to_raw["order_status_raw"]
    counts = top_values(df, status_col, n=200)
    counts.to_csv(export_eda / "status_value_counts.csv", index=False, encoding="utf-8-sig")
    mapped = (
        df[status_col].apply(lambda value: map_status_value(value, status_map))
        if status_col in df.columns
        else pd.DataFrame(columns=["order_status_stage", "order_status_code"])
    )
    review = pd.concat(
        [df.get(status_col, pd.Series(dtype="object")).rename("order_status_raw"), mapped], axis=1
    ).drop_duplicates()
    review.to_csv(export_mappings / "order_status_map_review.csv", index=False, encoding="utf-8-sig")
    unmapped = review[review["order_status_stage"] == "unknown"] if "order_status_stage" in review else pd.DataFrame()
    unmapped.to_csv(export_eda / "status_unmapped_values.csv", index=False, encoding="utf-8-sig")
    return counts, review, unmapped


def map_hospital_level_value(value: Any, hospital_level_map: dict[str, Any]) -> pd.Series:
    if pd.isna(value) or str(value).strip() == "":
        default = hospital_level_map["default"]
        return pd.Series({"hospital_level_label": default["label"], "hospital_level_code": default["code"]})
    rule = _keyword_match(value, hospital_level_map["rules"])
    if rule:
        return pd.Series({"hospital_level_label": rule["label"], "hospital_level_code": rule["code"]})
    return pd.Series({"hospital_level_label": "其他", "hospital_level_code": 9})


def analyze_hospital_level(
    df: pd.DataFrame,
    alias_to_raw: dict[str, str],
    hospital_level_map: dict[str, Any],
    export_eda: Path,
    export_mappings: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    col = alias_to_raw["hospital_level_raw"]
    counts = top_values(df, col, n=200)
    counts.to_csv(export_eda / "hospital_level_value_counts.csv", index=False, encoding="utf-8-sig")
    mapped = (
        df[col].apply(lambda value: map_hospital_level_value(value, hospital_level_map))
        if col in df.columns
        else pd.DataFrame(columns=["hospital_level_label", "hospital_level_code"])
    )
    review = pd.concat(
        [df.get(col, pd.Series(dtype="object")).rename("hospital_level_raw"), mapped], axis=1
    ).drop_duplicates()
    review.to_csv(export_mappings / "hospital_level_map.csv", index=False, encoding="utf-8-sig")
    unmapped = (
        review[review["hospital_level_label"].isin(["未知", "其他"])]
        if "hospital_level_label" in review
        else pd.DataFrame()
    )
    unmapped.to_csv(
        export_eda / "hospital_level_unmapped_values.csv", index=False, encoding="utf-8-sig"
    )
    return counts, review, unmapped


def one_to_one_report(df: pd.DataFrame, left: str, right: str, name: str) -> dict[str, Any]:
    if left not in df.columns or right not in df.columns:
        return {"metric": name, "left_distinct": np.nan, "right_distinct": np.nan, "multi_mapping_count": np.nan}
    tmp = (
        df[[left, right]]
        .dropna()
        .drop_duplicates()
        .groupby(left)[right]
        .nunique()
        .reset_index(name="right_distinct_count")
    )
    return {
        "metric": name,
        "left_distinct": int(df[left].nunique(dropna=True)),
        "right_distinct": int(df[right].nunique(dropna=True)),
        "multi_mapping_count": int((tmp["right_distinct_count"] > 1).sum()),
    }


def analyze_enterprise(df: pd.DataFrame, alias_to_raw: dict[str, str], export_eda: Path) -> pd.DataFrame:
    report = pd.DataFrame(
        [
            one_to_one_report(
                df,
                alias_to_raw["enterprise_code"],
                alias_to_raw["manufacturer_code"],
                "enterprise_code_to_manufacturer_code",
            ),
            one_to_one_report(
                df,
                alias_to_raw["manufacturer_code"],
                alias_to_raw["manufacturer_name"],
                "manufacturer_code_to_manufacturer_name",
            ),
            one_to_one_report(
                df,
                alias_to_raw["enterprise_code"],
                alias_to_raw["manufacturer_name"],
                "enterprise_code_to_manufacturer_name",
            ),
        ]
    )
    report.to_csv(export_eda / "enterprise_mapping_report.csv", index=False, encoding="utf-8-sig")
    return report


def build_drug_category_map(
    df: pd.DataFrame, alias_to_raw: dict[str, str], export_mappings: Path
) -> pd.DataFrame:
    counts = top_values(df, alias_to_raw["drug_category_raw"], n=200).rename(
        columns={"value": "drug_category_raw"}
    )
    counts["drug_category_code"] = range(1, len(counts) + 1)
    counts[["drug_category_raw", "drug_category_code", "count"]].to_csv(
        export_mappings / "drug_category_map.csv", index=False, encoding="utf-8-sig"
    )
    return counts


def map_ownership_value(value: Any) -> pd.Series:
    if pd.isna(value) or str(value).strip() == "":
        return pd.Series({"ownership_type_label": "未知", "ownership_type_code": -1})
    text_value = str(value)
    if "公立" in text_value:
        return pd.Series({"ownership_type_label": "公立", "ownership_type_code": 1})
    if "民营" in text_value or "私立" in text_value:
        return pd.Series({"ownership_type_label": "民营", "ownership_type_code": 2})
    return pd.Series({"ownership_type_label": "其他", "ownership_type_code": 9})


def build_ownership_map(
    df: pd.DataFrame, alias_to_raw: dict[str, str], export_mappings: Path
) -> pd.DataFrame:
    counts = top_values(df, alias_to_raw["ownership_type_raw"], n=200).rename(
        columns={"value": "ownership_type_raw"}
    )
    mapping = counts.join(counts["ownership_type_raw"].apply(map_ownership_value)) if not counts.empty else pd.DataFrame()
    mapping.to_csv(export_mappings / "ownership_map.csv", index=False, encoding="utf-8-sig")
    return mapping


def analyze_return_void(df: pd.DataFrame, alias_to_raw: dict[str, str], export_eda: Path) -> pd.DataFrame:
    return_s = pd.to_numeric(
        df.get(alias_to_raw["return_quantity"], pd.Series(index=df.index)), errors="coerce"
    ).fillna(0)
    void_s = pd.to_numeric(
        df.get(alias_to_raw["void_quantity"], pd.Series(index=df.index)), errors="coerce"
    ).fillna(0)
    report = pd.DataFrame(
        [
            {
                "field": "return_quantity",
                "non_zero_count": int((return_s != 0).sum()),
                "non_zero_rate": float((return_s != 0).mean()),
            },
            {
                "field": "void_quantity",
                "non_zero_count": int((void_s != 0).sum()),
                "non_zero_rate": float((void_s != 0).mean()),
            },
        ]
    )
    report.to_csv(export_eda / "return_void_quantity_report.csv", index=False, encoding="utf-8-sig")
    return report


def build_clean_table(
    df: pd.DataFrame,
    schema: dict[str, Any],
    raw_to_alias: dict[str, str],
    status_map: dict[str, Any],
    hospital_level_map: dict[str, Any],
    drug_category_counts: pd.DataFrame | None = None,
) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for raw, alias in raw_to_alias.items():
        if raw in df.columns:
            out[alias] = df[raw]
    if "purchase_time" in out.columns:
        out["purchase_time"] = pd.to_datetime(out["purchase_time"], errors="coerce")
    if "county_code" in out.columns:
        county = normalize_code(out["county_code"]).str.zfill(6)
        out["county_code"] = county
        out["province_code"] = county.str.slice(0, 2) + "0000"
        out["city_code"] = county.str.slice(0, 4) + "00"
    if "order_status_raw" in out.columns:
        out = out.join(out["order_status_raw"].apply(lambda value: map_status_value(value, status_map)))
        lifecycle_map = order_status_lifecycle_map_dataframe()
        lifecycle = out["order_status_raw"].apply(lambda value: map_status_lifecycle_value(value, lifecycle_map))
        for column in lifecycle.columns:
            out[column] = lifecycle[column].values
    if "hospital_level_raw" in out.columns:
        out = out.join(
            out["hospital_level_raw"].apply(
                lambda value: map_hospital_level_value(value, hospital_level_map)
            )
        )
    if "drug_category_raw" in out.columns and drug_category_counts is not None and not drug_category_counts.empty:
        category_map = dict(
            zip(drug_category_counts["drug_category_raw"].astype("string"), drug_category_counts["drug_category_code"])
        )
        out["drug_category_code"] = out["drug_category_raw"].astype("string").map(category_map)
    if "ownership_type_raw" in out.columns:
        out = out.join(out["ownership_type_raw"].apply(map_ownership_value))
    if "return_quantity" in out.columns:
        out["return_quantity"] = pd.to_numeric(out["return_quantity"], errors="coerce").fillna(0)
    clean_cols: list[str] = []
    for cols in schema["clean_columns"].values():
        clean_cols.extend(cols)
    clean_cols = [column for column in clean_cols if column in out.columns]
    return out[clean_cols].copy()


def save_clean_outputs(df_clean: pd.DataFrame, paths: CleaningPaths) -> None:
    paths.clean_parquet_path.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_parquet(paths.clean_parquet_path, index=False)
    df_clean.head(1000).to_csv(
        paths.export_clean / "bs_agent_dingdan_clean_sample.csv",
        index=False,
        encoding="utf-8-sig",
    )


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return pd.to_numeric(numerator, errors="coerce") / pd.to_numeric(denominator, errors="coerce").replace(0, np.nan)


def build_alias_table_from_raw(df_raw: pd.DataFrame, raw_to_alias: dict[str, str]) -> pd.DataFrame:
    """Build an alias-named working table directly from raw sample columns."""

    out = pd.DataFrame(index=df_raw.index)
    for raw, alias in raw_to_alias.items():
        if raw in df_raw.columns:
            out[alias] = df_raw[raw]
        elif alias in df_raw.columns:
            out[alias] = df_raw[alias]
    if "enterprise_code" in out.columns and "enterprise_code_raw" not in out.columns:
        out["enterprise_code_raw"] = out["enterprise_code"]
    return out


def add_v2_derived_fields(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in [
        "raw_sensitive_purchase_quantity",
        "raw_sensitive_delivery_quantity",
        "raw_sensitive_arrival_quantity",
        "raw_sensitive_purchase_amount",
        "raw_sensitive_delivery_amount",
        "raw_sensitive_arrival_amount",
        "return_quantity",
    ]:
        if column in out:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    if "county_code" in out:
        county = normalize_code(out["county_code"]).str.zfill(6)
        derived_province = county.str.slice(0, 2) + "0000"
        derived_city = county.str.slice(0, 4) + "00"
        raw_city = normalize_code(out["raw_city_code"]).str.zfill(6) if "raw_city_code" in out else pd.Series(pd.NA, index=out.index, dtype="string")
        out["county_code"] = county
        out["province_code"] = derived_province
        out["city_code"] = derived_city
        out["region_dirty_flag"] = (
            raw_city.notna() & derived_city.notna() & (raw_city != derived_city)
        ).astype(int)
    else:
        out["region_dirty_flag"] = 0
    if {"drug_code", "insurance_drug_code"}.issubset(out.columns):
        drug = normalize_code(out["drug_code"])
        insurance = normalize_code(out["insurance_drug_code"])
        out["drug_code_match_flag"] = np.select(
            [drug.isna() | insurance.isna(), drug == insurance],
            [-1, 1],
            default=0,
        )
        conflict = (
            pd.DataFrame({"drug_code": drug, "insurance_drug_code": insurance})
            .dropna()
            .drop_duplicates()
            .groupby("drug_code")["insurance_drug_code"]
            .nunique()
        )
        conflict_codes = set(conflict[conflict > 1].index)
        out["drug_code_conflict_flag"] = np.where(drug.isna(), -1, drug.isin(conflict_codes).astype(int))
    else:
        out["drug_code_match_flag"] = -1
        out["drug_code_conflict_flag"] = -1
    out["delivery_rate"] = _safe_ratio(
        out.get("raw_sensitive_delivery_quantity", pd.Series(index=out.index)),
        out.get("raw_sensitive_purchase_quantity", pd.Series(index=out.index)),
    )
    out["arrival_rate"] = _safe_ratio(
        out.get("raw_sensitive_arrival_quantity", pd.Series(index=out.index)),
        out.get("raw_sensitive_delivery_quantity", pd.Series(index=out.index)),
    )
    out["overall_arrival_rate"] = _safe_ratio(
        out.get("raw_sensitive_arrival_quantity", pd.Series(index=out.index)),
        out.get("raw_sensitive_purchase_quantity", pd.Series(index=out.index)),
    )
    out["delivery_amount_to_purchase_amount_ratio"] = _safe_ratio(
        out.get("raw_sensitive_delivery_amount", pd.Series(index=out.index)),
        out.get("raw_sensitive_purchase_amount", pd.Series(index=out.index)),
    )
    out["arrival_amount_to_delivery_amount_ratio"] = _safe_ratio(
        out.get("raw_sensitive_arrival_amount", pd.Series(index=out.index)),
        out.get("raw_sensitive_delivery_amount", pd.Series(index=out.index)),
    )
    out["arrival_amount_to_purchase_amount_ratio"] = _safe_ratio(
        out.get("raw_sensitive_arrival_amount", pd.Series(index=out.index)),
        out.get("raw_sensitive_purchase_amount", pd.Series(index=out.index)),
    )
    return out


def build_clean_model_audit_v2(
    df_raw: pd.DataFrame,
    paths: CleaningPaths,
    schema: dict[str, Any],
    raw_to_alias: dict[str, str],
    hospital_level_map: dict[str, Any],
    drug_category_counts: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    aliased = build_alias_table_from_raw(df_raw, raw_to_alias)
    if "purchase_time" in aliased.columns:
        aliased["purchase_time"] = pd.to_datetime(aliased["purchase_time"], errors="coerce")
    if "hospital_level_raw" in aliased.columns:
        aliased = aliased.join(
            aliased["hospital_level_raw"].apply(
                lambda value: map_hospital_level_value(value, hospital_level_map)
            )
        )
    if "drug_category_raw" in aliased.columns:
        if drug_category_counts is None or drug_category_counts.empty:
            drug_category_counts = top_values(aliased, "drug_category_raw", n=200).rename(
                columns={"value": "drug_category_raw"}
            )
            drug_category_counts["drug_category_code"] = range(1, len(drug_category_counts) + 1)
        category_map = dict(
            zip(
                drug_category_counts["drug_category_raw"].astype("string"),
                drug_category_counts["drug_category_code"],
            )
        )
        aliased["drug_category_code"] = aliased["drug_category_raw"].astype("string").map(category_map)
    if "ownership_type_raw" in aliased.columns:
        aliased = aliased.join(aliased["ownership_type_raw"].apply(map_ownership_value))
    if "return_quantity" in aliased.columns:
        aliased["return_quantity"] = pd.to_numeric(aliased["return_quantity"], errors="coerce").fillna(0)
    clean_work, _, _ = apply_order_status_lifecycle(aliased, paths.export_eda, paths.export_mappings)
    clean_work = add_v2_derived_fields(clean_work)
    clean_work["mapping_failure_reason"] = np.where(
        clean_work["order_phase_code"] == 0,
        "unknown_or_unmapped_status",
        np.where(clean_work["needs_manual_review"].astype(bool), "manual_review_status", ""),
    )
    clean_columns: list[str] = []
    for columns in schema["clean_columns"].values():
        clean_columns.extend(columns)
    derived_clean_columns = [
        "region_dirty_flag",
        "delivery_rate",
        "arrival_rate",
        "overall_arrival_rate",
        "delivery_amount_to_purchase_amount_ratio",
        "arrival_amount_to_delivery_amount_ratio",
        "arrival_amount_to_purchase_amount_ratio",
    ]
    clean_v2_columns = [column for column in clean_columns + derived_clean_columns if column in clean_work.columns]
    clean_v2 = clean_work[
        clean_v2_columns + [c for c in ["mapping_failure_reason"] if c in clean_work]
    ].copy()
    model_columns = [
        "row_uid",
        "order_detail_id",
        "purchase_time",
        "province_code",
        "city_code",
        "county_code",
        "region_dirty_flag",
        "hospital_code",
        "drug_code",
        "drug_category_code",
        "distributor_code",
        "manufacturer_code",
        "hospital_level_code",
        "ownership_type_code",
        "order_phase_code",
        "delivery_state_code",
        "order_terminal_flag",
        "order_failure_flag",
        "return_quantity",
        "raw_sensitive_purchase_quantity",
        "raw_sensitive_purchase_amount",
        "raw_sensitive_delivery_quantity",
        "raw_sensitive_delivery_amount",
        "raw_sensitive_arrival_quantity",
        "raw_sensitive_arrival_amount",
        "delivery_rate",
        "arrival_rate",
        "overall_arrival_rate",
        "delivery_amount_to_purchase_amount_ratio",
        "arrival_amount_to_delivery_amount_ratio",
        "arrival_amount_to_purchase_amount_ratio",
    ]
    model = clean_v2[[column for column in model_columns if column in clean_v2.columns]].copy()
    audit_columns = [
        "row_uid",
        "order_detail_id",
        "raw_province_code",
        "raw_city_code",
        "province_code",
        "city_code",
        "county_code",
        "region_dirty_flag",
        "order_status_raw",
        "order_status_norm",
        "order_phase_code",
        "order_phase_label",
        "delivery_state_code",
        "delivery_state_label",
        "order_terminal_flag",
        "order_failure_flag",
        "needs_manual_review",
        "mapping_failure_reason",
        "drug_code",
        "insurance_drug_code",
        "drug_code_match_flag",
        "drug_code_conflict_flag",
        "drug_category_raw",
        "drug_category_code",
        "product_name",
        "hospital_level_raw",
        "hospital_level_label",
        "hospital_level_code",
        "hospital_level_detail_raw",
        "ownership_type_raw",
        "ownership_type_code",
        "enterprise_code_raw",
        "manufacturer_code",
        "manufacturer_name",
        "distributor_code",
        "distributor_name",
        "delivery_rate",
        "arrival_rate",
        "overall_arrival_rate",
    ]
    audit = clean_work[[column for column in audit_columns if column in clean_work.columns]].copy()
    return clean_v2, model, audit


def build_numeric_desensitization_report_v2(df: pd.DataFrame, export_eda: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    df = add_v2_derived_fields(df)
    numeric_columns = [
        "raw_sensitive_purchase_quantity",
        "raw_sensitive_delivery_quantity",
        "raw_sensitive_arrival_quantity",
        "raw_sensitive_purchase_amount",
        "raw_sensitive_delivery_amount",
        "raw_sensitive_arrival_amount",
        "return_quantity",
    ]
    negative_samples = []
    for column in numeric_columns:
        if column in df:
            series = pd.to_numeric(df[column], errors="coerce")
            rows.append({"metric_group": "zero_rate", "metric": f"{column}_zero_rate", "value": float((series == 0).mean())})
            rows.append({"metric_group": "negative_rate", "metric": f"{column}_negative_rate", "value": float((series < 0).mean())})
            sample = df.loc[series < 0, [c for c in ["row_uid", "order_detail_id", "order_status_raw", column] if c in df.columns]].copy()
            sample["negative_field"] = column
            sample["negative_value"] = series[series < 0].values
            negative_samples.append(sample)
    negative_sample_df = pd.concat(negative_samples, ignore_index=True) if negative_samples else pd.DataFrame()
    negative_sample_df.to_csv(export_eda / "numeric_negative_samples_v2.csv", index=False, encoding="utf-8-sig")
    ratio_columns = [
        "delivery_rate",
        "arrival_rate",
        "overall_arrival_rate",
        "delivery_amount_to_purchase_amount_ratio",
        "arrival_amount_to_delivery_amount_ratio",
        "arrival_amount_to_purchase_amount_ratio",
    ]
    for column in ratio_columns:
        series = pd.to_numeric(df[column], errors="coerce")
        non_null = series.dropna()
        rows.extend(
            [
                {"metric_group": column, "metric": "count", "value": int(series.count())},
                {"metric_group": column, "metric": "min", "value": series.min()},
                {"metric_group": column, "metric": "p25", "value": series.quantile(0.25)},
                {"metric_group": column, "metric": "p50", "value": series.quantile(0.5)},
                {"metric_group": column, "metric": "p75", "value": series.quantile(0.75)},
                {"metric_group": column, "metric": "p95", "value": series.quantile(0.95)},
                {"metric_group": column, "metric": "max", "value": series.max()},
                {
                    "metric_group": column,
                    "metric": f"{column}_gt_1_rate",
                    "value": float((non_null > 1).mean()) if len(non_null) else np.nan,
                },
            ]
        )
    if "order_phase_code" in df:
        for phase, group in df.groupby("order_phase_code", dropna=False):
            for column in ["delivery_rate", "arrival_rate", "overall_arrival_rate"]:
                series = pd.to_numeric(group[column], errors="coerce")
                rows.append({"metric_group": f"order_phase_code={phase}", "metric": f"{column}_count", "value": int(series.count())})
                rows.append({"metric_group": f"order_phase_code={phase}", "metric": f"{column}_p50", "value": series.quantile(0.5)})
                rows.append({"metric_group": f"order_phase_code={phase}", "metric": f"{column}_p95", "value": series.quantile(0.95)})
    contradictions = {
        "received_but_arrival_quantity_zero": (df.get("delivery_state_code") == 5) & (df.get("raw_sensitive_arrival_quantity") == 0),
        "dispatched_but_delivery_quantity_zero": df.get("delivery_state_code").isin([3, 4]) & (df.get("raw_sensitive_delivery_quantity") == 0),
        "cancelled_or_failed_but_has_delivery_or_arrival": (df.get("order_phase_code") == 100)
        & ((df.get("raw_sensitive_delivery_quantity") > 0) | (df.get("raw_sensitive_arrival_quantity") > 0)),
    }
    for metric, mask in contradictions.items():
        rows.append({"metric_group": "status_quantity_contradiction", "metric": metric, "value": int(mask.sum())})
    report = pd.DataFrame(rows)
    report.to_csv(export_eda / "numeric_desensitization_report_v2.csv", index=False, encoding="utf-8-sig")
    return report


def save_v2_outputs(
    df_raw: pd.DataFrame,
    paths: CleaningPaths,
    schema: dict[str, Any],
    raw_to_alias: dict[str, str],
    hospital_level_map: dict[str, Any],
    drug_category_counts: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    clean_v2, model, audit = build_clean_model_audit_v2(
        df_raw, paths, schema, raw_to_alias, hospital_level_map, drug_category_counts
    )
    clean_v2.to_csv(paths.export_clean / "bs_agent_dingdan_clean_sample_v2.csv", index=False, encoding="utf-8-sig")
    model.to_csv(paths.export_clean / "bs_agent_dingdan_model_sample.csv", index=False, encoding="utf-8-sig")
    audit.to_csv(paths.export_clean / "bs_agent_dingdan_audit_sample.csv", index=False, encoding="utf-8-sig")
    numeric_v2 = build_numeric_desensitization_report_v2(clean_v2, paths.export_eda)
    profile = build_profile_v2(clean_v2, model, audit, paths)
    (paths.export_eda / "bs_agent_dingdan_profile_v2.md").write_text(profile, encoding="utf-8")
    return clean_v2, model, audit, numeric_v2, profile


def build_profile_v2(df_clean: pd.DataFrame, model: pd.DataFrame, audit: pd.DataFrame, paths: CleaningPaths) -> str:
    total_rows = len(df_clean)
    mapped_rows = int((df_clean.get("order_phase_code", pd.Series(dtype=int)) != 0).sum())
    mapping_coverage = mapped_rows / total_rows if total_rows else np.nan
    row_uid_unique = bool(df_clean["row_uid"].is_unique) if "row_uid" in df_clean else None
    detail_unique = bool(df_clean["order_detail_id"].is_unique) if "order_detail_id" in df_clean else None
    contradiction_report = pd.read_csv(paths.export_eda / "numeric_desensitization_report_v2.csv")
    contradictions = contradiction_report[
        contradiction_report["metric_group"] == "status_quantity_contradiction"
    ]
    contradiction_lines = "\n".join(
        f"- {row.metric}: {row.value}" for row in contradictions.itertuples(index=False)
    )
    return f"""# BS_Agent_DingDan 二次清洗 profile v2

## 范围限制

- 当前只基于本地 sample：{total_rows} 行，不代表全量最终结论。
- 文件未加密，但数量、金额和价格字段存在脱敏。
- 本轮不做全量 SQL 读取，不推进 detector，不做算法建模。

## 关键结论

- row_uid 在 sample 中唯一：{row_uid_unique}
- order_detail_id 在 sample 中唯一：{detail_unique}
- 企业编码已判为无效字段，不进入 clean/model；如原始样本提供，仅在 audit 中保留为 enterprise_code_raw。
- 地区编码优先使用 county_code，province_code/city_code 从 county_code 派生；冲突暂按 region_dirty_flag 脏数据处理。
- 药品编码和药品医保编码不可合并；model 使用 drug_code，audit 保留匹配/冲突标记。
- drug_category_code 可用于 model，但不是 product_line_code。
- 商品名、医院名称、企业名称、raw/label 类文字列不进入 model。
- 作废数量当前不进入 model。

## 订单状态生命周期映射

- 映射覆盖率：{mapping_coverage}
- 映射表：`exports/mappings/order_status_lifecycle_map.csv`
- 覆盖率报告：`exports/eda/order_status_mapping_coverage.csv`
- 可疑映射报告：`exports/eda/order_status_suspicious_mapping.csv`

## 状态与数量矛盾样本数量

{contradiction_lines}

## 三张输出表

- clean_sample_v2：{len(df_clean)} 行，{df_clean.shape[1]} 列，保留 raw/label/code，供人工阅读。
- model_sample：{len(model)} 行，{model.shape[1]} 列，只保留 ID、code、flag 和数值/比例字段。
- audit_sample：{len(audit)} 行，{audit.shape[1]} 列，保留追溯和复核字段。
"""


def build_quality_report(
    schema: dict[str, Any],
    basic: dict[str, Any],
    status_review: pd.DataFrame,
    status_unmapped: pd.DataFrame,
    hospital_review: pd.DataFrame,
    hospital_unmapped: pd.DataFrame,
) -> str:
    algorithm_usable_fields = [column["alias"] for column in schema["columns"] if column.get("algorithm_usable")]
    algorithm_unusable_fields = [
        column["alias"] for column in schema["columns"] if not column.get("algorithm_usable")
    ]
    status_coverage = 1 - (len(status_unmapped) / max(len(status_review), 1))
    hospital_coverage = 1 - (len(hospital_unmapped) / max(len(hospital_review), 1))
    return f"""# BS_Agent_DingDan 数据质量报告

## 总体规模

- 行数：{basic['row_count']}
- 列数：{basic['column_count']}
- 采购时间范围：{basic['purchase_time_min']} ~ {basic['purchase_time_max']}

## 唯一标识符结论

详见 `exports/eda/id_duplicate_report.csv` 和 `exports/eda/order_detail_duplicate_samples.csv`。如订单明细ID重复，当前仅标记为可能代表同一订单明细的多次状态/生命周期记录，需要进一步确认。

## 地区编码一致性结论

地区映射表：`exports/mappings/region_code_map.csv`；冲突检查：`exports/eda/region_code_conflicts.csv`。

## 药品编码与医保编码一致性结论

详见 `exports/eda/drug_code_vs_insurance_code_report.csv`。

## 数值字段脱敏破坏程度结论

详见 `exports/eda/numeric_desensitization_report.csv`。新脱敏方式保留了同类字段之间的比例关系：数量字段之间可计算 delivery_rate、arrival_rate、overall_arrival_rate，金额字段之间可比较相对关系；但不保留金额字段与数量字段之间的真实价格关系。

## 订单状态归类覆盖率

- 覆盖率：{status_coverage}
- 未匹配值：`exports/eda/status_unmapped_values.csv`
- 人工复核表：`exports/mappings/order_status_map_review.csv`

## 医疗机构等级解析覆盖率

- 覆盖率：{hospital_coverage}
- 使用字段：医疗机构等级
- 不可信字段：医疗机构详细等级，仅保留 raw/audit
- 映射表：`exports/mappings/hospital_level_map.csv`

## 企业/生产企业字段关系

详见 `exports/eda/enterprise_mapping_report.csv`。确认前不直接删除原始字段。

## 药品类别与所有制形式

- 药品类别映射：`exports/mappings/drug_category_map.csv`
- 所有制映射：`exports/mappings/ownership_map.csv`

## 当前可用于算法的字段

{', '.join(algorithm_usable_fields)}

## 当前不可用于算法的字段

{', '.join(algorithm_unusable_fields)}

## 待向数据提供者确认的问题

1. 订单明细ID重复是否代表订单生命周期记录。
2. 数量字段是否统一乘随机数 q、金额字段是否统一乘随机数 m，以及采购价格是否单独脱敏。
3. 企业编码、生产企业编码、生产企业之间的真实业务关系。
4. 医疗机构详细等级是否确认为错误字段，未来是否会修复。
"""


def save_quality_report(report: str, export_eda: Path) -> Path:
    path = export_eda / "bs_agent_dingdan_profile.md"
    path.write_text(report, encoding="utf-8")
    return path
