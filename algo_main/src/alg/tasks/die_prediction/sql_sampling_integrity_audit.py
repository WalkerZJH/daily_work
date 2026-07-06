"""SQL sampling integrity audit for alive prediction source data.

This report-only module checks whether the local alive-prediction data looks
like a row-level SQL sample rather than an entity-complete history extract. It
does not train models, tune parameters, export full SQL detail, or modify any
M1-M7 artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import re
import traceback
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

from alg.cleaning.bs_agent_dingdan import (
    build_column_maps,
    load_env,
    load_yaml,
    quote_sqlserver_identifier,
)


ENTITY_COLS = ["manufacturer_code", "hospital_code", "drug_code"]
LOCAL_DATASET_CANDIDATES = [
    "data/03_cleaned/bs_agent_dingdan_model_base.parquet",
    "data/03_cleaned/bs_agent_dingdan_clean.parquet",
    "data/01_raw/BS_Agent_DingDan.parquet",
    "data/04_facts/alive_prediction/fact_purchase_event__drug_code.parquet",
]
FEATURE_TABLE_CANDIDATES = [
    "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/cutoff_2024-01_2024-12/feature_table__status0.parquet",
    "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/cutoff_2020-01_2024-12/feature_table__status0.parquet",
]
CANDIDATE_POOL_CANDIDATES = [
    "reports/alive_prediction_candidate_pool_v1/recurring_business_priority_candidates.csv",
    "reports/alive_prediction_candidate_pool_v1/recurring_business_priority_candidates_by_horizon.csv",
]
OUTPUT_FILES = [
    "sql_sampling_integrity_summary.md",
    "sql_connection_audit.md",
    "sql_table_profile.csv",
    "sql_monthly_distribution.csv",
    "local_dataset_profile.csv",
    "local_vs_sql_entity_coverage.csv",
    "entity_history_completeness_audit.csv",
    "sampled_entity_sql_history_gap.csv",
    "sampling_bias_by_manufacturer.csv",
    "sampling_bias_by_month.csv",
    "sampling_bias_by_entity_age.csv",
    "sql_entity_complete_extraction_plan.md",
    "next_data_action_decision.md",
]


@dataclass(frozen=True)
class SqlAuditConfig:
    project_root: Path
    output_dir: Path
    sample_entity_count: int = 500
    batch_size: int = 100
    query_timeout: int = 60
    dry_run: bool = False
    skip_sql: bool = False


@dataclass(frozen=True)
class SqlContext:
    sql_database_url: str | None
    sql_table: str
    raw_to_alias: dict[str, str]
    alias_to_raw: dict[str, str]
    helper_source: str


@dataclass
class AuditResult:
    sql_connected: bool
    sql_total_row_count: int | None
    sql_purchase_time_min: str | None
    sql_purchase_time_max: str | None
    local_row_count: int
    local_purchase_time_min: str | None
    local_purchase_time_max: str | None
    sampled_entity_count: int
    entity_history_complete_rate: float | None
    order_count_coverage_mean: float | None
    order_count_coverage_median: float | None
    first_purchase_lag_days_median: float | None
    last_purchase_gap_days_median: float | None
    top_n_or_ordered_sample_risk: str
    entity_history_incomplete_risk: str
    manufacturer_sampling_skew: bool | None
    time_sampling_skew: bool | None
    entity_age_sampling_skew: bool | None
    model_result_contamination_risk: str
    recommended_extraction_plan: str


def write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def read_parquet_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except (FileNotFoundError, OSError, ValueError, ImportError):
        return pd.DataFrame()


def mask_database_url(url: str | None) -> str:
    """Return a secret-safe database URL representation."""

    if not url:
        return "<not configured>"
    try:
        parsed = make_url(url)
        database = parsed.database or "<database>"
        return f"{parsed.drivername}://<user>:***@<host>/{database}"
    except Exception:
        masked = re.sub(r"(://[^:/@;]+:)[^@;]+(@)", r"\1***\2", str(url))
        masked = re.sub(r"(://)[^:/@;]+(:)", r"\1<user>\2", masked)
        masked = re.sub(r"(@)[^/;?\s]+", r"\1<host>", masked)
        masked = re.sub(r"(?i)(password|pwd)\s*=\s*[^;]+", r"\1=***", masked)
        return masked


def sanitize_message(message: str, sql_database_url: str | None = None) -> str:
    out = str(message)
    if sql_database_url:
        out = out.replace(sql_database_url, mask_database_url(sql_database_url))
    out = re.sub(r"(://[^:/@;]+:)[^@;\s]+(@)", r"\1***\2", out)
    out = re.sub(r"(?i)(password|pwd)\s*=\s*[^;\s]+", r"\1=***", out)
    return out


def load_sql_context(project_root: Path) -> SqlContext:
    raw_to_alias: dict[str, str] = {}
    alias_to_raw: dict[str, str] = {}
    schema_path = project_root / "configs/data_schema/bs_agent_dingdan_schema.yaml"
    if schema_path.exists():
        schema = load_yaml(schema_path)
        raw_to_alias, alias_to_raw, _raw_columns = build_column_maps(schema)
    sql_database_url, sql_table = load_env(project_root)
    return SqlContext(
        sql_database_url=sql_database_url,
        sql_table=sql_table,
        raw_to_alias=raw_to_alias,
        alias_to_raw=alias_to_raw,
        helper_source="alg.cleaning.bs_agent_dingdan.load_env + configs/data_schema/bs_agent_dingdan_schema.yaml",
    )


def sql_col(context: SqlContext, alias: str, table_alias: str | None = None) -> str:
    raw_name = context.alias_to_raw.get(alias, alias)
    quoted = quote_sqlserver_identifier(raw_name)
    return f"{table_alias}.{quoted}" if table_alias else quoted


def sql_cast_text(expr: str) -> str:
    return f"CAST({expr} AS nvarchar(255))"


def sql_date_expr(context: SqlContext, table_alias: str | None = None) -> str:
    return f"TRY_CONVERT(datetime2, {sql_col(context, 'purchase_time', table_alias=table_alias)})"


def sql_entity_expr(context: SqlContext, table_alias: str | None = None) -> str:
    parts = [
        f"COALESCE({sql_cast_text(sql_col(context, col, table_alias=table_alias))}, N'__NULL__')"
        for col in ENTITY_COLS
    ]
    return "CONCAT(" + ", N'|', ".join(parts) + ")"


def create_sql_engine_safe(sql_database_url: str | None) -> Engine | None:
    if not sql_database_url:
        return None
    return create_engine(sql_database_url)


def query_sql_dataframe(
    engine: Engine,
    sql: str,
    params: dict[str, Any] | None = None,
    query_timeout: int | None = None,
) -> pd.DataFrame:
    with engine.connect() as conn:
        if query_timeout:
            conn = conn.execution_options(timeout=int(query_timeout))
        return pd.read_sql_query(text(sql), conn, params=params or {})


def sql_table_profile_query(context: SqlContext) -> str:
    date_expr = sql_date_expr(context)
    entity_expr = sql_entity_expr(context)
    return f"""
SELECT
    COUNT_BIG(*) AS sql_total_row_count,
    MIN({date_expr}) AS purchase_time_min,
    MAX({date_expr}) AS purchase_time_max,
    COUNT(DISTINCT {sql_cast_text(sql_col(context, 'manufacturer_code'))}) AS manufacturer_count,
    COUNT(DISTINCT {sql_cast_text(sql_col(context, 'hospital_code'))}) AS hospital_count,
    COUNT(DISTINCT {sql_cast_text(sql_col(context, 'drug_code'))}) AS drug_code_count,
    COUNT(DISTINCT {entity_expr}) AS entity_count
FROM {quote_sqlserver_identifier(context.sql_table)}
"""


def sql_monthly_distribution_query(context: SqlContext) -> str:
    date_expr = sql_date_expr(context)
    month_expr = f"CONVERT(char(7), {date_expr}, 120)"
    entity_expr = sql_entity_expr(context)
    return f"""
SELECT
    {month_expr} AS purchase_month,
    COUNT_BIG(*) AS sql_row_count,
    COUNT(DISTINCT {entity_expr}) AS sql_entity_count
FROM {quote_sqlserver_identifier(context.sql_table)}
WHERE {date_expr} IS NOT NULL
GROUP BY {month_expr}
ORDER BY purchase_month
"""


def sql_manufacturer_distribution_query(context: SqlContext, top_n: int = 200) -> str:
    manufacturer = sql_cast_text(sql_col(context, "manufacturer_code"))
    entity_expr = sql_entity_expr(context)
    return f"""
SELECT TOP ({int(top_n)})
    {manufacturer} AS manufacturer_code,
    COUNT_BIG(*) AS sql_row_count,
    COUNT(DISTINCT {entity_expr}) AS sql_entity_count
FROM {quote_sqlserver_identifier(context.sql_table)}
GROUP BY {manufacturer}
ORDER BY sql_row_count DESC
"""


def sql_entity_age_distribution_query(context: SqlContext) -> str:
    date_expr = sql_date_expr(context)
    mfg = sql_cast_text(sql_col(context, "manufacturer_code"))
    hosp = sql_cast_text(sql_col(context, "hospital_code"))
    drug = sql_cast_text(sql_col(context, "drug_code"))
    month_expr = f"CONVERT(char(7), {date_expr}, 120)"
    table = quote_sqlserver_identifier(context.sql_table)
    return f"""
WITH entity_history AS (
    SELECT
        {mfg} AS manufacturer_code,
        {hosp} AS hospital_code,
        {drug} AS drug_code,
        COUNT_BIG(*) AS order_count,
        MIN({date_expr}) AS first_purchase_time,
        MAX({date_expr}) AS last_purchase_time,
        COUNT(DISTINCT {month_expr}) AS active_month_count
    FROM {table}
    WHERE {date_expr} IS NOT NULL
    GROUP BY {mfg}, {hosp}, {drug}
)
SELECT
    CASE
        WHEN DATEDIFF(month, first_purchase_time, last_purchase_time) + 1 < 3 THEN '00_0_2m'
        WHEN DATEDIFF(month, first_purchase_time, last_purchase_time) + 1 < 6 THEN '01_3_5m'
        WHEN DATEDIFF(month, first_purchase_time, last_purchase_time) + 1 < 12 THEN '02_6_11m'
        WHEN DATEDIFF(month, first_purchase_time, last_purchase_time) + 1 < 24 THEN '03_12_23m'
        WHEN DATEDIFF(month, first_purchase_time, last_purchase_time) + 1 < 36 THEN '04_24_35m'
        ELSE '05_36m_plus'
    END AS entity_age_bucket,
    COUNT_BIG(*) AS sql_entity_count,
    AVG(CAST(order_count AS float)) AS sql_avg_order_count,
    AVG(CAST(active_month_count AS float)) AS sql_avg_active_month_count
FROM entity_history
GROUP BY
    CASE
        WHEN DATEDIFF(month, first_purchase_time, last_purchase_time) + 1 < 3 THEN '00_0_2m'
        WHEN DATEDIFF(month, first_purchase_time, last_purchase_time) + 1 < 6 THEN '01_3_5m'
        WHEN DATEDIFF(month, first_purchase_time, last_purchase_time) + 1 < 12 THEN '02_6_11m'
        WHEN DATEDIFF(month, first_purchase_time, last_purchase_time) + 1 < 24 THEN '03_12_23m'
        WHEN DATEDIFF(month, first_purchase_time, last_purchase_time) + 1 < 36 THEN '04_24_35m'
        ELSE '05_36m_plus'
    END
ORDER BY entity_age_bucket
"""


def sampled_entity_sql_history_query(context: SqlContext, keys: pd.DataFrame) -> tuple[str, dict[str, Any]]:
    values: list[str] = []
    params: dict[str, Any] = {}
    for i, row in keys.reset_index(drop=True).iterrows():
        values.append(f"(:m{i}, :h{i}, :d{i})")
        params[f"m{i}"] = str(row["manufacturer_code"])
        params[f"h{i}"] = str(row["hospital_code"])
        params[f"d{i}"] = str(row["drug_code"])
    if not values:
        raise ValueError("sampled entity query requires at least one key")
    date_expr = sql_date_expr(context, table_alias="t")
    month_expr = f"CONVERT(char(7), {date_expr}, 120)"
    table = quote_sqlserver_identifier(context.sql_table)
    mfg = sql_cast_text(sql_col(context, "manufacturer_code", table_alias="t"))
    hosp = sql_cast_text(sql_col(context, "hospital_code", table_alias="t"))
    drug = sql_cast_text(sql_col(context, "drug_code", table_alias="t"))
    sql = f"""
WITH sample_entity(manufacturer_code, hospital_code, drug_code) AS (
    SELECT * FROM (VALUES {", ".join(values)}) AS v(manufacturer_code, hospital_code, drug_code)
),
entity_history AS (
    SELECT
        s.manufacturer_code,
        s.hospital_code,
        s.drug_code,
        COUNT_BIG({sql_col(context, 'manufacturer_code', table_alias='t')}) AS sql_order_count_total,
        MIN({date_expr}) AS sql_first_purchase_time,
        MAX({date_expr}) AS sql_last_purchase_time,
        COUNT(DISTINCT {month_expr}) AS sql_active_month_count
    FROM sample_entity s
    LEFT JOIN {table} t
        ON {mfg} = s.manufacturer_code
       AND {hosp} = s.hospital_code
       AND {drug} = s.drug_code
    GROUP BY s.manufacturer_code, s.hospital_code, s.drug_code
)
SELECT * FROM entity_history
ORDER BY manufacturer_code, hospital_code, drug_code
"""
    return sql, params


def normalize_entity_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "drug_code" not in out.columns and "drug_group" in out.columns:
        out["drug_code"] = out["drug_group"]
    for col in ENTITY_COLS:
        if col not in out.columns:
            out[col] = "__MISSING__"
        out[col] = out[col].astype("string").fillna("__MISSING__").str.strip()
    return out


def add_entity_key(df: pd.DataFrame) -> pd.DataFrame:
    out = normalize_entity_columns(df)
    out["entity_key"] = out[ENTITY_COLS].astype(str).agg("|".join, axis=1)
    return out


def months_observed_from_dates(first: pd.Series, last: pd.Series) -> pd.Series:
    first_ts = pd.to_datetime(first, errors="coerce")
    last_ts = pd.to_datetime(last, errors="coerce")
    months = (last_ts.dt.year - first_ts.dt.year) * 12 + (last_ts.dt.month - first_ts.dt.month) + 1
    return months.where(first_ts.notna() & last_ts.notna())


def month_string(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.to_period("M").astype(str).replace("NaT", np.nan)


def standardize_raw_local_columns(df: pd.DataFrame, raw_to_alias: dict[str, str]) -> pd.DataFrame:
    if not raw_to_alias:
        return df.copy()
    rename = {raw: alias for raw, alias in raw_to_alias.items() if raw in df.columns and alias not in df.columns}
    return df.rename(columns=rename)


def find_local_dataset(project_root: Path, raw_to_alias: dict[str, str] | None = None) -> tuple[pd.DataFrame, Path | None]:
    for rel in LOCAL_DATASET_CANDIDATES:
        path = project_root / rel
        if path.exists():
            df = read_parquet_or_empty(path)
            if not df.empty:
                return standardize_raw_local_columns(df, raw_to_alias or {}), path
    return pd.DataFrame(), None


def local_entity_aggregate(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                *ENTITY_COLS,
                "local_order_count_total",
                "local_first_purchase_time",
                "local_last_purchase_time",
                "local_active_month_count",
                "local_months_observed",
            ]
        )
    work = add_entity_key(df)
    if "purchase_time" not in work.columns:
        work["purchase_time"] = pd.NaT
    work["purchase_time"] = pd.to_datetime(work["purchase_time"], errors="coerce")
    if "purchase_month" in work.columns:
        work["purchase_month_norm"] = month_string(work["purchase_month"])
    else:
        work["purchase_month_norm"] = month_string(work["purchase_time"])
    agg = (
        work.groupby(ENTITY_COLS, dropna=False)
        .agg(
            local_order_count_total=("entity_key", "size"),
            local_first_purchase_time=("purchase_time", "min"),
            local_last_purchase_time=("purchase_time", "max"),
            local_active_month_count=("purchase_month_norm", pd.Series.nunique),
        )
        .reset_index()
    )
    agg["local_months_observed"] = months_observed_from_dates(
        agg["local_first_purchase_time"], agg["local_last_purchase_time"]
    )
    return agg


def profile_local_dataset(df: pd.DataFrame, source_path: Path | None) -> tuple[pd.DataFrame, dict[str, Any]]:
    if df.empty:
        summary = {
            "local_source_path": str(source_path) if source_path else None,
            "local_row_count": 0,
            "purchase_time_min": None,
            "purchase_time_max": None,
            "manufacturer_count": 0,
            "hospital_count": 0,
            "drug_code_count": 0,
            "entity_count": 0,
        }
        return pd.DataFrame([{"metric": k, "value": v} for k, v in summary.items()]), summary
    work = add_entity_key(df)
    if "purchase_time" not in work.columns:
        work["purchase_time"] = pd.NaT
    work["purchase_time"] = pd.to_datetime(work["purchase_time"], errors="coerce")
    ent = local_entity_aggregate(work)
    summary = {
        "local_source_path": str(source_path) if source_path else None,
        "local_row_count": int(len(work)),
        "purchase_time_min": _date_to_string(work["purchase_time"].min()),
        "purchase_time_max": _date_to_string(work["purchase_time"].max()),
        "manufacturer_count": int(work["manufacturer_code"].nunique(dropna=True)),
        "hospital_count": int(work["hospital_code"].nunique(dropna=True)),
        "drug_code_count": int(work["drug_code"].nunique(dropna=True)),
        "entity_count": int(work["entity_key"].nunique(dropna=True)),
    }
    for prefix, values in {
        "rows_per_entity": ent["local_order_count_total"],
        "active_months_per_entity": ent["local_active_month_count"],
        "months_observed_per_entity": ent["local_months_observed"],
    }.items():
        for q_name, q in [("p10", 0.10), ("p25", 0.25), ("p50", 0.50), ("p75", 0.75), ("p90", 0.90)]:
            summary[f"{prefix}_{q_name}"] = _safe_quantile(values, q)
        summary[f"{prefix}_mean"] = _safe_mean(values)
    rows = [{"metric": k, "value": v} for k, v in summary.items()]
    for col, label in [
        ("manufacturer_code", "top_manufacturer"),
        ("hospital_code", "top_hospital"),
        ("drug_code", "top_drug_code"),
    ]:
        top = work[col].value_counts(dropna=False).head(10)
        for i, (value, count) in enumerate(top.items(), start=1):
            rows.append({"metric": f"{label}_{i}", "value": str(value)})
            rows.append({"metric": f"{label}_{i}_row_share", "value": float(count / len(work))})
    return pd.DataFrame(rows), summary


def local_monthly_distribution(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["purchase_month", "local_row_count", "local_entity_count"])
    work = add_entity_key(df)
    if "purchase_month" in work.columns:
        work["purchase_month"] = month_string(work["purchase_month"])
    else:
        work["purchase_month"] = month_string(work.get("purchase_time", pd.Series(index=work.index)))
    out = (
        work.dropna(subset=["purchase_month"])
        .groupby("purchase_month", dropna=False)
        .agg(local_row_count=("entity_key", "size"), local_entity_count=("entity_key", "nunique"))
        .reset_index()
        .sort_values("purchase_month")
    )
    return out


def local_manufacturer_distribution(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["manufacturer_code", "local_row_count", "local_entity_count"])
    work = add_entity_key(df)
    out = (
        work.groupby("manufacturer_code", dropna=False)
        .agg(local_row_count=("entity_key", "size"), local_entity_count=("entity_key", "nunique"))
        .reset_index()
        .sort_values("local_row_count", ascending=False)
    )
    return out


def local_entity_age_distribution(local_agg: pd.DataFrame) -> pd.DataFrame:
    if local_agg.empty:
        return pd.DataFrame(
            columns=[
                "entity_age_bucket",
                "local_entity_count",
                "local_avg_order_count",
                "local_avg_active_month_count",
            ]
        )
    work = local_agg.copy()
    work["entity_age_bucket"] = pd.cut(
        pd.to_numeric(work["local_months_observed"], errors="coerce"),
        bins=[-math.inf, 2, 5, 11, 23, 35, math.inf],
        labels=["00_0_2m", "01_3_5m", "02_6_11m", "03_12_23m", "04_24_35m", "05_36m_plus"],
        right=True,
    ).astype(str)
    return (
        work.groupby("entity_age_bucket", dropna=False)
        .agg(
            local_entity_count=("manufacturer_code", "size"),
            local_avg_order_count=("local_order_count_total", "mean"),
            local_avg_active_month_count=("local_active_month_count", "mean"),
        )
        .reset_index()
        .sort_values("entity_age_bucket")
    )


def compare_monthly_distribution(local_months: pd.DataFrame, sql_months: pd.DataFrame) -> pd.DataFrame:
    local = local_months.copy()
    sql = sql_months.copy()
    for col in ["purchase_month", "local_row_count", "local_entity_count"]:
        if col not in local.columns:
            local[col] = pd.Series(dtype="object" if col == "purchase_month" else "float64")
    for col in ["purchase_month", "sql_row_count", "sql_entity_count"]:
        if col not in sql.columns:
            sql[col] = pd.Series(dtype="object" if col == "purchase_month" else "float64")
    out = local.merge(sql, on="purchase_month", how="outer").fillna(
        {"local_row_count": 0, "local_entity_count": 0, "sql_row_count": 0, "sql_entity_count": 0}
    )
    local_total = out["local_row_count"].sum()
    sql_total = out["sql_row_count"].sum()
    out["local_row_share"] = np.where(local_total > 0, out["local_row_count"] / local_total, np.nan)
    out["sql_row_share"] = np.where(sql_total > 0, out["sql_row_count"] / sql_total, np.nan)
    out["row_share_delta"] = out["local_row_share"] - out["sql_row_share"]
    out["local_vs_sql_row_share_ratio"] = safe_divide(out["local_row_share"], out["sql_row_share"])
    return out.sort_values("purchase_month")


def compare_manufacturer_distribution(local_mfg: pd.DataFrame, sql_mfg: pd.DataFrame) -> pd.DataFrame:
    local_mfg = local_mfg.copy()
    sql_mfg = sql_mfg.copy()
    for col in ["manufacturer_code", "local_row_count", "local_entity_count"]:
        if col not in local_mfg.columns:
            local_mfg[col] = pd.Series(dtype="object" if col == "manufacturer_code" else "float64")
    for col in ["manufacturer_code", "sql_row_count", "sql_entity_count"]:
        if col not in sql_mfg.columns:
            sql_mfg[col] = pd.Series(dtype="object" if col == "manufacturer_code" else "float64")
    out = local_mfg.merge(sql_mfg, on="manufacturer_code", how="outer").fillna(
        {"local_row_count": 0, "local_entity_count": 0, "sql_row_count": 0, "sql_entity_count": 0}
    )
    local_total = out["local_row_count"].sum()
    sql_total = out["sql_row_count"].sum()
    out["local_row_share"] = np.where(local_total > 0, out["local_row_count"] / local_total, np.nan)
    out["sql_row_share"] = np.where(sql_total > 0, out["sql_row_count"] / sql_total, np.nan)
    out["row_share_delta"] = out["local_row_share"] - out["sql_row_share"]
    out["abs_row_share_delta"] = out["row_share_delta"].abs()
    out["local_vs_sql_row_share_ratio"] = safe_divide(out["local_row_share"], out["sql_row_share"])
    return out.sort_values("abs_row_share_delta", ascending=False)


def compare_entity_age_distribution(local_age: pd.DataFrame, sql_age: pd.DataFrame) -> pd.DataFrame:
    local_age = local_age.copy()
    sql_age = sql_age.copy()
    for col in [
        "entity_age_bucket",
        "local_entity_count",
        "local_avg_order_count",
        "local_avg_active_month_count",
    ]:
        if col not in local_age.columns:
            local_age[col] = pd.Series(dtype="object" if col == "entity_age_bucket" else "float64")
    for col in [
        "entity_age_bucket",
        "sql_entity_count",
        "sql_avg_order_count",
        "sql_avg_active_month_count",
    ]:
        if col not in sql_age.columns:
            sql_age[col] = pd.Series(dtype="object" if col == "entity_age_bucket" else "float64")
    out = local_age.merge(sql_age, on="entity_age_bucket", how="outer").fillna(
        {
            "local_entity_count": 0,
            "local_avg_order_count": np.nan,
            "local_avg_active_month_count": np.nan,
            "sql_entity_count": 0,
            "sql_avg_order_count": np.nan,
            "sql_avg_active_month_count": np.nan,
        }
    )
    local_total = out["local_entity_count"].sum()
    sql_total = out["sql_entity_count"].sum()
    out["local_entity_share"] = np.where(local_total > 0, out["local_entity_count"] / local_total, np.nan)
    out["sql_entity_share"] = np.where(sql_total > 0, out["sql_entity_count"] / sql_total, np.nan)
    out["entity_share_delta"] = out["local_entity_share"] - out["sql_entity_share"]
    return out.sort_values("entity_age_bucket")


def sample_local_entities(
    project_root: Path,
    local_agg: pd.DataFrame,
    sample_entity_count: int,
) -> pd.DataFrame:
    if local_agg.empty or sample_entity_count <= 0:
        return pd.DataFrame(columns=[*ENTITY_COLS, "sample_reason"])
    samples: list[pd.DataFrame] = []
    per_reason = max(20, sample_entity_count // 4)
    top = local_agg.sort_values("local_order_count_total", ascending=False).head(per_reason).copy()
    top["sample_reason"] = "high_frequency_local_entity"
    samples.append(top[[*ENTITY_COLS, "sample_reason"]])
    low_history = local_agg[local_agg["local_order_count_total"].le(2)].head(per_reason).copy()
    low_history["sample_reason"] = "low_history_local_entity"
    samples.append(low_history[[*ENTITY_COLS, "sample_reason"]])
    feature_keys = read_optional_feature_history_keys(project_root, per_reason)
    if not feature_keys.empty:
        samples.append(feature_keys)
    candidate_keys = read_optional_candidate_keys(project_root, per_reason)
    if not candidate_keys.empty:
        samples.append(candidate_keys)
    already = pd.concat(samples, ignore_index=True) if samples else pd.DataFrame(columns=[*ENTITY_COLS, "sample_reason"])
    remaining = max(0, sample_entity_count - already[ENTITY_COLS].drop_duplicates().shape[0])
    if remaining:
        random_pool = local_agg.sample(min(remaining, len(local_agg)), random_state=20260702).copy()
        random_pool["sample_reason"] = "random_local_entity"
        samples.append(random_pool[[*ENTITY_COLS, "sample_reason"]])
    out = pd.concat(samples, ignore_index=True) if samples else pd.DataFrame(columns=[*ENTITY_COLS, "sample_reason"])
    out = normalize_entity_columns(out)
    out = out.drop_duplicates(subset=ENTITY_COLS, keep="first").head(sample_entity_count)
    return out[[*ENTITY_COLS, "sample_reason"]]


def read_optional_feature_history_keys(project_root: Path, limit: int) -> pd.DataFrame:
    for rel in FEATURE_TABLE_CANDIDATES:
        path = project_root / rel
        if not path.exists():
            continue
        df = read_parquet_or_empty(path)
        if df.empty:
            continue
        df = normalize_entity_columns(df)
        reason = "history_insufficient_or_cold_start_feature"
        mask = pd.Series(False, index=df.index)
        if "cold_start_flag" in df.columns:
            mask = mask | df["cold_start_flag"].fillna(False).astype(bool)
        if "purchase_count_asof_cutoff" in df.columns:
            mask = mask | pd.to_numeric(df["purchase_count_asof_cutoff"], errors="coerce").le(2)
        if "months_observed_asof_cutoff" in df.columns:
            mask = mask | pd.to_numeric(df["months_observed_asof_cutoff"], errors="coerce").le(3)
        keys = df.loc[mask, ENTITY_COLS].drop_duplicates().head(limit).copy()
        if not keys.empty:
            keys["sample_reason"] = reason
            return keys
    return pd.DataFrame(columns=[*ENTITY_COLS, "sample_reason"])


def read_optional_candidate_keys(project_root: Path, limit: int) -> pd.DataFrame:
    for rel in CANDIDATE_POOL_CANDIDATES:
        path = project_root / rel
        df = read_csv_or_empty(path)
        if df.empty:
            continue
        df = normalize_entity_columns(df)
        keys = df[ENTITY_COLS].drop_duplicates().head(limit).copy()
        if not keys.empty:
            keys["sample_reason"] = "m1_candidate_entity"
            return keys
    return pd.DataFrame(columns=[*ENTITY_COLS, "sample_reason"])


def compute_history_completeness(local_agg: pd.DataFrame, sql_agg: pd.DataFrame, sampled: pd.DataFrame) -> pd.DataFrame:
    if sampled.empty:
        return pd.DataFrame(
            columns=[
                *ENTITY_COLS,
                "sample_reason",
                "local_order_count_total",
                "sql_order_count_total",
                "order_count_coverage_ratio",
                "history_complete_flag",
            ]
        )
    local = normalize_entity_columns(local_agg)
    sql = normalize_entity_columns(sql_agg) if not sql_agg.empty else pd.DataFrame(columns=ENTITY_COLS)
    out = sampled.merge(local, on=ENTITY_COLS, how="left")
    if sql.empty:
        out["sql_order_count_total"] = np.nan
        out["sql_first_purchase_time"] = pd.NaT
        out["sql_last_purchase_time"] = pd.NaT
        out["sql_active_month_count"] = np.nan
    else:
        out = out.merge(sql, on=ENTITY_COLS, how="left")
    for col in ["local_order_count_total", "sql_order_count_total", "local_active_month_count", "sql_active_month_count"]:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["sql_months_observed"] = months_observed_from_dates(
        out.get("sql_first_purchase_time", pd.Series(index=out.index)),
        out.get("sql_last_purchase_time", pd.Series(index=out.index)),
    )
    out["order_count_coverage_ratio"] = safe_divide(out["local_order_count_total"], out["sql_order_count_total"])
    out["active_month_coverage_ratio"] = safe_divide(out["local_active_month_count"], out["sql_active_month_count"])
    local_first = pd.to_datetime(out.get("local_first_purchase_time", pd.Series(index=out.index)), errors="coerce")
    sql_first = pd.to_datetime(out.get("sql_first_purchase_time", pd.Series(index=out.index)), errors="coerce")
    local_last = pd.to_datetime(out.get("local_last_purchase_time", pd.Series(index=out.index)), errors="coerce")
    sql_last = pd.to_datetime(out.get("sql_last_purchase_time", pd.Series(index=out.index)), errors="coerce")
    out["local_first_purchase_lag_days"] = (local_first - sql_first).dt.days
    out["local_last_purchase_gap_days"] = (sql_last - local_last).dt.days
    history_complete = (
        out["order_count_coverage_ratio"].ge(0.95)
        & out["local_first_purchase_lag_days"].abs().le(7)
        & out["local_last_purchase_gap_days"].abs().le(7)
    )
    out["history_complete_flag"] = history_complete
    out["history_gap_note"] = np.select(
        [
            out["sql_order_count_total"].isna(),
            out["sql_order_count_total"].eq(0),
            history_complete,
            out["local_first_purchase_lag_days"].gt(7),
            out["local_last_purchase_gap_days"].gt(7),
            out["order_count_coverage_ratio"].lt(0.95),
        ],
        [
            "sql_not_queried_or_unavailable",
            "entity_not_found_in_sql",
            "history_complete_by_rule",
            "old_history_missing_in_local",
            "recent_history_missing_in_local",
            "local_order_count_below_sql",
        ],
        default="history_incomplete_other",
    )
    out["history_complete_flag"] = out["history_complete_flag"].map(bool).astype(object)
    return out


def local_vs_sql_entity_coverage(audit: pd.DataFrame) -> pd.DataFrame:
    if audit.empty:
        return pd.DataFrame(
            columns=[
                "sampled_entity_count",
                "entity_history_complete_count",
                "entity_history_complete_rate",
                "order_count_coverage_ratio_mean",
                "order_count_coverage_ratio_median",
                "first_purchase_lag_days_median",
                "last_purchase_gap_days_median",
            ]
        )
    complete_flag = audit["history_complete_flag"].map(bool)
    return pd.DataFrame(
        [
            {
                "sampled_entity_count": int(len(audit)),
                "entity_history_complete_count": int(complete_flag.sum()),
                "entity_history_complete_rate": _safe_mean(complete_flag.astype(float)),
                "order_count_coverage_ratio_mean": _safe_mean(audit["order_count_coverage_ratio"]),
                "order_count_coverage_ratio_median": _safe_median(audit["order_count_coverage_ratio"]),
                "first_purchase_lag_days_median": _safe_median(audit["local_first_purchase_lag_days"]),
                "last_purchase_gap_days_median": _safe_median(audit["local_last_purchase_gap_days"]),
                "old_history_missing_rate": _safe_mean(audit["local_first_purchase_lag_days"].gt(7).astype(float)),
                "recent_history_missing_rate": _safe_mean(audit["local_last_purchase_gap_days"].gt(7).astype(float)),
                "local_order_count_below_sql_rate": _safe_mean(audit["order_count_coverage_ratio"].lt(0.95).astype(float)),
            }
        ]
    )


def dry_run_local_dataset() -> pd.DataFrame:
    rows = []
    for month in pd.period_range("2023-01", "2024-12", freq="M"):
        rows.append(
            {
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_code": "d1",
                "purchase_time": month.to_timestamp() + pd.Timedelta(days=4),
                "purchase_month": month.to_timestamp(),
            }
        )
    rows.extend(
        [
            {
                "manufacturer_code": "m1",
                "hospital_code": "h2",
                "drug_code": "d2",
                "purchase_time": pd.Timestamp("2024-08-10"),
                "purchase_month": pd.Timestamp("2024-08-01"),
            },
            {
                "manufacturer_code": "m2",
                "hospital_code": "h3",
                "drug_code": "d3",
                "purchase_time": pd.Timestamp("2024-12-10"),
                "purchase_month": pd.Timestamp("2024-12-01"),
            },
        ]
    )
    return pd.DataFrame(rows)


def dry_run_sql_frames(local_agg: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sql_profile = pd.DataFrame(
        [
            {
                "sql_total_row_count": 260,
                "purchase_time_min": pd.Timestamp("2022-01-01"),
                "purchase_time_max": pd.Timestamp("2025-12-31"),
                "manufacturer_count": 3,
                "hospital_count": 5,
                "drug_code_count": 6,
                "entity_count": 20,
            }
        ]
    )
    sql_months = pd.DataFrame(
        {
            "purchase_month": pd.period_range("2022-01", "2025-12", freq="M").astype(str),
            "sql_row_count": [5] * 48,
            "sql_entity_count": [4] * 48,
        }
    )
    sql_mfg = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m2", "m3"],
            "sql_row_count": [120, 80, 60],
            "sql_entity_count": [8, 7, 5],
        }
    )
    sql_age = pd.DataFrame(
        {
            "entity_age_bucket": ["00_0_2m", "03_12_23m", "05_36m_plus"],
            "sql_entity_count": [4, 6, 10],
            "sql_avg_order_count": [1.5, 8.0, 20.0],
            "sql_avg_active_month_count": [1.2, 6.5, 18.0],
        }
    )
    sql_agg = local_agg.copy()
    if not sql_agg.empty:
        sql_agg = sql_agg.rename(
            columns={
                "local_order_count_total": "sql_order_count_total",
                "local_first_purchase_time": "sql_first_purchase_time",
                "local_last_purchase_time": "sql_last_purchase_time",
                "local_active_month_count": "sql_active_month_count",
            }
        )
        sql_agg["sql_order_count_total"] = sql_agg["sql_order_count_total"] + 2
        sql_agg["sql_first_purchase_time"] = pd.to_datetime(sql_agg["sql_first_purchase_time"]) - pd.Timedelta(days=120)
    return sql_profile, sql_months, sql_mfg, sql_age, sql_agg


def run_sql_sampling_integrity_audit(
    project_root: str | Path,
    output_dir: str | Path,
    *,
    sample_entity_count: int = 500,
    batch_size: int = 100,
    query_timeout: int = 60,
    dry_run: bool = False,
    skip_sql: bool = False,
) -> dict[str, Any]:
    config = SqlAuditConfig(
        project_root=Path(project_root).resolve(),
        output_dir=Path(output_dir).resolve(),
        sample_entity_count=sample_entity_count,
        batch_size=batch_size,
        query_timeout=query_timeout,
        dry_run=dry_run,
        skip_sql=skip_sql,
    )
    config.output_dir.mkdir(parents=True, exist_ok=True)
    context = load_sql_context(config.project_root)
    connection_status = {
        "url_configured": bool(context.sql_database_url),
        "masked_database_url": mask_database_url(context.sql_database_url),
        "sql_table": context.sql_table,
        "helper_source": context.helper_source,
        "sql_connected": False,
        "failure_reason": None,
        "notebook_sample_evidence": "notebooks/01_BS_Agent_DingDan_EDA_and_Cleaning.ipynb uses sample_mode=True, max_rows=100000",
        "pipeline_sample_evidence": "alg.cleaning.bs_agent_dingdan_pipeline._read_sql_projected uses SELECT TOP (...) when max_rows/sample_mode is set",
    }

    if dry_run:
        local_df = dry_run_local_dataset()
        local_source_path = Path("<dry_run>")
    else:
        local_df, local_source_path = find_local_dataset(config.project_root, context.raw_to_alias)
    local_profile, local_profile_summary = profile_local_dataset(local_df, local_source_path)
    local_agg = local_entity_aggregate(local_df)
    local_months = local_monthly_distribution(local_df)
    local_mfg = local_manufacturer_distribution(local_df)
    local_age = local_entity_age_distribution(local_agg)
    sampled = sample_local_entities(config.project_root, local_agg, config.sample_entity_count)

    sql_profile = pd.DataFrame()
    sql_months = pd.DataFrame()
    sql_mfg = pd.DataFrame()
    sql_age = pd.DataFrame()
    sql_sample_agg = pd.DataFrame()

    if dry_run:
        sql_profile, sql_months, sql_mfg, sql_age, sql_sample_agg = dry_run_sql_frames(local_agg)
        connection_status["sql_connected"] = True
    elif skip_sql:
        connection_status["failure_reason"] = "SQL query skipped by --skip-sql."
    else:
        try:
            engine = create_sql_engine_safe(context.sql_database_url)
            if engine is None:
                raise RuntimeError("SQL_DATABASE_URL is not configured.")
            sql_profile = query_sql_dataframe(engine, sql_table_profile_query(context), query_timeout=config.query_timeout)
            sql_months = query_sql_dataframe(
                engine, sql_monthly_distribution_query(context), query_timeout=config.query_timeout
            )
            sql_mfg = query_sql_dataframe(
                engine, sql_manufacturer_distribution_query(context), query_timeout=config.query_timeout
            )
            sql_age = query_sql_dataframe(
                engine, sql_entity_age_distribution_query(context), query_timeout=config.query_timeout
            )
            if not sampled.empty:
                sql_sample_agg = query_sampled_entity_history(
                    engine, context, sampled, config.batch_size, config.query_timeout
                )
            connection_status["sql_connected"] = True
        except Exception as exc:  # pragma: no cover - exercised through integration runs
            connection_status["failure_reason"] = sanitize_message(
                "".join(traceback.format_exception_only(type(exc), exc)).strip(),
                context.sql_database_url,
            )

    coverage_audit = compute_history_completeness(local_agg, sql_sample_agg, sampled)
    coverage_summary = local_vs_sql_entity_coverage(coverage_audit)
    month_bias = compare_monthly_distribution(local_months, sql_months)
    mfg_bias = compare_manufacturer_distribution(local_mfg, sql_mfg)
    age_bias = compare_entity_age_distribution(local_age, sql_age)
    risks = assess_sampling_risks(
        local_profile_summary=local_profile_summary,
        sql_profile=sql_profile,
        coverage_summary=coverage_summary,
        month_bias=month_bias,
        mfg_bias=mfg_bias,
        age_bias=age_bias,
        sql_connected=bool(connection_status["sql_connected"]),
    )
    result = build_audit_result(
        connection_status=connection_status,
        sql_profile=sql_profile,
        local_profile_summary=local_profile_summary,
        sampled=sampled,
        coverage_summary=coverage_summary,
        risks=risks,
    )

    write_csv(config.output_dir / "sql_table_profile.csv", normalize_sql_profile(sql_profile))
    write_csv(config.output_dir / "sql_monthly_distribution.csv", normalize_sql_months(sql_months))
    write_csv(config.output_dir / "local_dataset_profile.csv", local_profile)
    write_csv(config.output_dir / "local_vs_sql_entity_coverage.csv", coverage_summary)
    write_csv(config.output_dir / "entity_history_completeness_audit.csv", coverage_audit)
    write_csv(config.output_dir / "sampled_entity_sql_history_gap.csv", sample_history_gap(coverage_audit))
    write_csv(config.output_dir / "sampling_bias_by_manufacturer.csv", mfg_bias)
    write_csv(config.output_dir / "sampling_bias_by_month.csv", month_bias)
    write_csv(config.output_dir / "sampling_bias_by_entity_age.csv", age_bias)
    write_text(config.output_dir / "sql_connection_audit.md", render_connection_audit(connection_status))
    write_text(
        config.output_dir / "sql_sampling_integrity_summary.md",
        render_summary(result, risks, connection_status, local_source_path),
    )
    write_text(config.output_dir / "sql_entity_complete_extraction_plan.md", render_extraction_plan(result))
    write_text(config.output_dir / "next_data_action_decision.md", render_next_data_action_decision(result, risks))

    return {
        "result": result,
        "connection_status": connection_status,
        "local_profile": local_profile,
        "sql_profile": normalize_sql_profile(sql_profile),
        "sampled_entities": sampled,
        "coverage_audit": coverage_audit,
        "coverage_summary": coverage_summary,
        "month_bias": month_bias,
        "manufacturer_bias": mfg_bias,
        "entity_age_bias": age_bias,
        "risks": risks,
        "output_dir": config.output_dir,
    }


def query_sampled_entity_history(
    engine: Engine,
    context: SqlContext,
    sampled: pd.DataFrame,
    batch_size: int,
    query_timeout: int | None = None,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    keys = normalize_entity_columns(sampled)[ENTITY_COLS].drop_duplicates().reset_index(drop=True)
    for start in range(0, len(keys), max(1, int(batch_size))):
        batch = keys.iloc[start : start + max(1, int(batch_size))]
        sql, params = sampled_entity_sql_history_query(context, batch)
        frames.append(query_sql_dataframe(engine, sql, params=params, query_timeout=query_timeout))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def normalize_sql_profile(sql_profile: pd.DataFrame) -> pd.DataFrame:
    if sql_profile.empty:
        return pd.DataFrame(
            columns=[
                "sql_total_row_count",
                "purchase_time_min",
                "purchase_time_max",
                "manufacturer_count",
                "hospital_count",
                "drug_code_count",
                "entity_count",
            ]
        )
    out = sql_profile.copy()
    for col in ["purchase_time_min", "purchase_time_max"]:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce").map(_date_to_string)
    return out


def normalize_sql_months(sql_months: pd.DataFrame) -> pd.DataFrame:
    if sql_months.empty:
        return pd.DataFrame(columns=["purchase_month", "sql_row_count", "sql_entity_count"])
    out = sql_months.copy()
    out["purchase_month"] = out["purchase_month"].astype(str)
    return out


def sample_history_gap(audit: pd.DataFrame, limit: int = 500) -> pd.DataFrame:
    if audit.empty:
        return audit.copy()
    sort_cols = ["history_complete_flag", "order_count_coverage_ratio", "local_first_purchase_lag_days"]
    available_sort_cols = [c for c in sort_cols if c in audit.columns]
    return audit.sort_values(available_sort_cols, ascending=[True] * len(available_sort_cols)).head(limit)


def assess_sampling_risks(
    *,
    local_profile_summary: dict[str, Any],
    sql_profile: pd.DataFrame,
    coverage_summary: pd.DataFrame,
    month_bias: pd.DataFrame,
    mfg_bias: pd.DataFrame,
    age_bias: pd.DataFrame,
    sql_connected: bool,
) -> dict[str, Any]:
    local_rows = int(local_profile_summary.get("local_row_count") or 0)
    top_n_risk = "high" if 95_000 <= local_rows <= 105_000 else "medium"
    evidence = ["notebook_and_pipeline_use_select_top_when_sample_mode_or_max_rows_is_set"]
    if not sql_connected:
        entity_risk = "unknown_sql_unavailable"
        time_skew = None
        mfg_skew = None
        age_skew = None
        contamination = "cannot_rule_out"
    else:
        complete_rate = _coverage_value(coverage_summary, "entity_history_complete_rate")
        order_cov = _coverage_value(coverage_summary, "order_count_coverage_ratio_median")
        if complete_rate is not None and complete_rate < 0.80:
            entity_risk = "high"
        elif order_cov is not None and order_cov < 0.95:
            entity_risk = "high"
        elif complete_rate is not None and complete_rate >= 0.95:
            entity_risk = "low"
        else:
            entity_risk = "medium"
        max_month_delta = _safe_abs_max(month_bias.get("row_share_delta", pd.Series(dtype=float)))
        max_mfg_delta = _safe_abs_max(mfg_bias.get("row_share_delta", pd.Series(dtype=float)))
        max_age_delta = _safe_abs_max(age_bias.get("entity_share_delta", pd.Series(dtype=float)))
        time_skew = bool(max_month_delta is not None and max_month_delta > 0.05)
        mfg_skew = bool(max_mfg_delta is not None and max_mfg_delta > 0.05)
        age_skew = bool(max_age_delta is not None and max_age_delta > 0.05)
        if entity_risk == "high" or time_skew or mfg_skew or age_skew:
            contamination = "likely"
        else:
            contamination = "not_primary_based_on_audit"
    local_min = pd.to_datetime(local_profile_summary.get("purchase_time_min"), errors="coerce")
    local_max = pd.to_datetime(local_profile_summary.get("purchase_time_max"), errors="coerce")
    if not sql_profile.empty:
        sql_min = pd.to_datetime(sql_profile.iloc[0].get("purchase_time_min"), errors="coerce")
        sql_max = pd.to_datetime(sql_profile.iloc[0].get("purchase_time_max"), errors="coerce")
        if pd.notna(sql_min) and pd.notna(local_min) and local_min > sql_min + pd.Timedelta(days=30):
            evidence.append("local_first_purchase_time_later_than_sql_min")
            top_n_risk = "high"
        if pd.notna(sql_max) and pd.notna(local_max) and local_max < sql_max - pd.Timedelta(days=30):
            evidence.append("local_last_purchase_time_earlier_than_sql_max")
            top_n_risk = "high"
    interval_distortion = "high" if entity_risk == "high" else "unknown" if not sql_connected else "medium_or_low"
    return {
        "top_n_or_ordered_sample_risk": top_n_risk,
        "top_n_risk_evidence": "; ".join(evidence),
        "entity_history_incomplete_risk": entity_risk,
        "recent_period_overrepresented": time_skew,
        "manufacturer_sampling_skew": mfg_skew,
        "time_sampling_skew": time_skew,
        "entity_age_sampling_skew": age_skew,
        "interval_feature_distortion_risk": interval_distortion,
        "model_result_contamination_risk": contamination,
    }


def build_audit_result(
    *,
    connection_status: dict[str, Any],
    sql_profile: pd.DataFrame,
    local_profile_summary: dict[str, Any],
    sampled: pd.DataFrame,
    coverage_summary: pd.DataFrame,
    risks: dict[str, Any],
) -> AuditResult:
    sql_total = None
    sql_min = None
    sql_max = None
    if not sql_profile.empty:
        row = sql_profile.iloc[0]
        sql_total = _safe_int(row.get("sql_total_row_count"))
        sql_min = _date_to_string(pd.to_datetime(row.get("purchase_time_min"), errors="coerce"))
        sql_max = _date_to_string(pd.to_datetime(row.get("purchase_time_max"), errors="coerce"))
    complete_rate = _coverage_value(coverage_summary, "entity_history_complete_rate")
    mean_cov = _coverage_value(coverage_summary, "order_count_coverage_ratio_mean")
    median_cov = _coverage_value(coverage_summary, "order_count_coverage_ratio_median")
    first_lag = _coverage_value(coverage_summary, "first_purchase_lag_days_median")
    last_gap = _coverage_value(coverage_summary, "last_purchase_gap_days_median")
    recommended = "manufacturer_complete_then_entity_complete"
    if risks["entity_history_incomplete_risk"] == "low" and risks["model_result_contamination_risk"] == "not_primary_based_on_audit":
        recommended = "continue_full_universe_interval_backtest_with_current_data"
    elif not connection_status["sql_connected"]:
        recommended = "repair_sql_connection_or_export_aggregate_audit_tables_first"
    return AuditResult(
        sql_connected=bool(connection_status["sql_connected"]),
        sql_total_row_count=sql_total,
        sql_purchase_time_min=sql_min,
        sql_purchase_time_max=sql_max,
        local_row_count=int(local_profile_summary.get("local_row_count") or 0),
        local_purchase_time_min=local_profile_summary.get("purchase_time_min"),
        local_purchase_time_max=local_profile_summary.get("purchase_time_max"),
        sampled_entity_count=int(len(sampled)),
        entity_history_complete_rate=complete_rate,
        order_count_coverage_mean=mean_cov,
        order_count_coverage_median=median_cov,
        first_purchase_lag_days_median=first_lag,
        last_purchase_gap_days_median=last_gap,
        top_n_or_ordered_sample_risk=str(risks["top_n_or_ordered_sample_risk"]),
        entity_history_incomplete_risk=str(risks["entity_history_incomplete_risk"]),
        manufacturer_sampling_skew=risks["manufacturer_sampling_skew"],
        time_sampling_skew=risks["time_sampling_skew"],
        entity_age_sampling_skew=risks["entity_age_sampling_skew"],
        model_result_contamination_risk=str(risks["model_result_contamination_risk"]),
        recommended_extraction_plan=recommended,
    )


def render_connection_audit(status: dict[str, Any]) -> str:
    connection_line = "success" if status["sql_connected"] else "failed_or_skipped"
    failure = status.get("failure_reason") or "none"
    return f"""# SQL Connection Audit

## Connection Status

- SQL_DATABASE_URL configured: {bool(status["url_configured"])}
- SQL_DATABASE_URL masked: `{status["masked_database_url"]}`
- SQL_TABLE: `{status["sql_table"]}`
- helper reused: {status["helper_source"]}
- SQL connection status: {connection_line}
- failure reason: {failure}

## Notebook / Pipeline Evidence

- Notebook evidence: {status["notebook_sample_evidence"]}
- Pipeline evidence: {status["pipeline_sample_evidence"]}

No password or full connection string is written by this audit.
"""


def render_summary(
    result: AuditResult,
    risks: dict[str, Any],
    connection_status: dict[str, Any],
    local_source_path: Path | None,
) -> str:
    sql_status = "connected" if result.sql_connected else "unavailable"
    return f"""# SQL Sampling Integrity Summary

## Scope

This audit checks whether the local alive-prediction data is an entity-complete history extract or a row-level SQL sample. It only profiles data and SQL aggregates; it does not train or tune any model.

## Data Sources

- Local source used: `{local_source_path}`
- SQL status: {sql_status}
- Local rows: {result.local_row_count}
- Local purchase_time range: {result.local_purchase_time_min} to {result.local_purchase_time_max}
- SQL total rows: {fmt(result.sql_total_row_count)}
- SQL purchase_time range: {fmt(result.sql_purchase_time_min)} to {fmt(result.sql_purchase_time_max)}
- Sampled entities for SQL history audit: {result.sampled_entity_count}

## Key Findings

- Current notebook/pipeline evidence is consistent with row-level sampling: `sample_mode=True`, `max_rows=100000`, and `SELECT TOP (...)`.
- TOP N / ordered sample risk: {result.top_n_or_ordered_sample_risk}
- Entity history incomplete risk: {result.entity_history_incomplete_risk}
- Entity history complete rate: {fmt_float(result.entity_history_complete_rate)}
- Mean / median order-count coverage: {fmt_float(result.order_count_coverage_mean)} / {fmt_float(result.order_count_coverage_median)}
- Median first-purchase lag days: {fmt_float(result.first_purchase_lag_days_median)}
- Median last-purchase gap days: {fmt_float(result.last_purchase_gap_days_median)}
- Manufacturer skew risk: {fmt_bool(result.manufacturer_sampling_skew)}
- Time skew risk: {fmt_bool(result.time_sampling_skew)}
- Entity-age skew risk: {fmt_bool(result.entity_age_sampling_skew)}
- Interval feature distortion risk: {risks["interval_feature_distortion_risk"]}
- Model-result contamination risk: {result.model_result_contamination_risk}

## Answers To Core Questions

1. Current local data is strongly suspected to originate from SQL row-level TOP N sampling because the notebook and pipeline use that path.
2. Entity-complete coverage is {fmt_float(result.entity_history_complete_rate)} when SQL evidence is available; if SQL is unavailable, this remains unproven.
3. For sampled entities, SQL-vs-local history gaps are written to `entity_history_completeness_audit.csv` and `sampled_entity_sql_history_gap.csv`.
4. Time, manufacturer, and entity-age bias checks are written to the `sampling_bias_*` CSV files.
5. Low AUC / weak rank ordering can be contaminated by incomplete entity history when order counts, observed months, recency, interval, ADI, CV2, and labels are computed on truncated histories.
6. Recommended next extraction path: {result.recommended_extraction_plan}.

## Model Impact Analysis

If entity histories are truncated, `purchase_count_asof_cutoff`, `active_month_count_asof_cutoff`, `months_observed_asof_cutoff`, `months_since_first_purchase_asof_cutoff`, median interval, ADI/CV2, and frequency-decay features can all be biased. Labels can also be distorted when the apparent absence of future purchases is caused by extraction boundaries rather than real non-repeat behavior.

That can explain low global logistic AUC, low candidate-level AUC, interval baseline coverage gaps, high history_not_available or cold-start rates, inflated intermittent/lumpy classification, and apparently acceptable ECE with weak ranking.

## Limitations

- SQL connection failure reason: {connection_status.get("failure_reason") or "none"}
- This audit does not export full SQL detail and only samples entity-level history aggregates.
"""


def render_extraction_plan(result: AuditResult) -> str:
    return f"""# SQL Entity-Complete Extraction Plan

## Recommended Sequence

Recommendation: `{result.recommended_extraction_plan}`.

## Plan A: Entity-Complete Sample

1. Select a controlled list of entity keys from SQL: `manufacturer_code x hospital_code x drug_code`.
2. Pull every order for those entities across the full available time range.
3. Use this for algorithm development, sequence features, interval features, and leakage-safe backtests.
4. Advantage: bounded data volume and complete histories. Limitation: full-universe recall is still sampled.

## Plan B: Manufacturer-Complete Subset

1. Select several stable manufacturers.
2. Pull all hospitals, drugs, and orders for those manufacturers across the full available time range.
3. Use this to validate the stable-enterprise service-scope hypothesis.
4. Advantage: realistic customer/service scope. Limitation: manufacturer selection can skew global conclusions.

## Plan C: Time-Window-Complete Extraction

1. Pull every order in a full time window, for example 2020-01 through 2025-12.
2. Build features and labels only within that window.
3. Use this for full-universe candidate recall and coverage backtests.
4. Advantage: best for production-like full-universe recall. Limitation: data volume may be large and old history before the window remains truncated.

## Plan D: Hybrid Recommended

1. Start with a manufacturer-complete subset to validate stable service scope.
2. Add an entity-complete sample to stress-test low-history and lumpy/intermittent entities.
3. Move to time-window-complete extraction when SQL volume and runtime are confirmed.

This sequence avoids tuning models on potentially truncated histories and gives a clean bridge to full-universe interval/survival evaluation.
"""


def render_next_data_action_decision(result: AuditResult, risks: dict[str, Any]) -> str:
    if not result.sql_connected:
        decision = "SQL evidence is unavailable, so data sampling risk cannot be ruled out. Repair SQL access or export aggregate audit tables before continuing algorithm conclusions."
        can_continue = "No. Continue only with local-only exploratory diagnostics, not final full-universe algorithm decisions."
    elif result.entity_history_incomplete_risk == "high":
        decision = "Entity history is incomplete for enough sampled entities that model tuning should pause."
        can_continue = "No. Re-extract entity-complete or manufacturer-complete data before full_universe_interval_backtest is treated as reliable."
    else:
        decision = "The audit does not identify entity history incompleteness as the primary blocker."
        can_continue = "Yes, current data can continue into full_universe_interval_backtest, while keeping row-level TOP N evidence documented."
    return f"""# Next Data Action Decision

## Decision

{decision}

## Direct Answers

1. Current local data is suspected row-level SQL sample: yes, because notebook/pipeline use `SELECT TOP` with `sample_mode=True` / `max_rows=100000`.
2. Current local data is entity-history complete: {completion_answer(result)}.
3. Current model results may be polluted by sampling: {result.model_result_contamination_risk}.
4. Pause model tuning: {pause_answer(result)}.
5. Re-extract data: {reextract_answer(result)}.
6. Recommended extraction: {result.recommended_extraction_plan}.
7. Continue full_universe_interval_backtest: {can_continue}
8. Fix data before algorithm: {fix_data_first_answer(result)}.

## Risk Flags

- top_n_or_ordered_sample_risk: {result.top_n_or_ordered_sample_risk}
- entity_history_incomplete_risk: {result.entity_history_incomplete_risk}
- recent_period_overrepresented: {fmt_bool(risks["recent_period_overrepresented"])}
- manufacturer_sampling_skew: {fmt_bool(result.manufacturer_sampling_skew)}
- entity_age_sampling_skew: {fmt_bool(result.entity_age_sampling_skew)}
- interval_feature_distortion_risk: {risks["interval_feature_distortion_risk"]}
"""


def completion_answer(result: AuditResult) -> str:
    if not result.sql_connected:
        return "unknown; SQL audit unavailable"
    if result.entity_history_incomplete_risk == "low":
        return "likely yes for sampled entities"
    return f"no or not reliable; complete rate={fmt_float(result.entity_history_complete_rate)}"


def pause_answer(result: AuditResult) -> str:
    return "yes" if (not result.sql_connected or result.entity_history_incomplete_risk == "high") else "not required by this audit"


def reextract_answer(result: AuditResult) -> str:
    return "yes" if (not result.sql_connected or result.entity_history_incomplete_risk in {"high", "medium"}) else "optional"


def fix_data_first_answer(result: AuditResult) -> str:
    return "yes" if (not result.sql_connected or result.entity_history_incomplete_risk == "high") else "not necessarily"


def safe_divide(num: Any, den: Any) -> Any:
    n = pd.to_numeric(num, errors="coerce")
    d = pd.to_numeric(den, errors="coerce")
    with np.errstate(divide="ignore", invalid="ignore"):
        out = n / d
    if isinstance(out, pd.Series):
        return out.where(d.ne(0))
    return out if d != 0 else np.nan


def _date_to_string(value: Any) -> str | None:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.strftime("%Y-%m-%d")


def _safe_quantile(values: pd.Series, q: float) -> float | None:
    nums = pd.to_numeric(values, errors="coerce").dropna()
    if nums.empty:
        return None
    return float(nums.quantile(q))


def _safe_mean(values: Any) -> float | None:
    nums = pd.to_numeric(values, errors="coerce").dropna()
    if len(nums) == 0:
        return None
    return float(nums.mean())


def _safe_median(values: Any) -> float | None:
    nums = pd.to_numeric(values, errors="coerce").dropna()
    if len(nums) == 0:
        return None
    return float(nums.median())


def _safe_abs_max(values: Any) -> float | None:
    nums = pd.to_numeric(values, errors="coerce").dropna()
    if len(nums) == 0:
        return None
    return float(nums.abs().max())


def _safe_int(value: Any) -> int | None:
    if pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coverage_value(coverage_summary: pd.DataFrame, column: str) -> float | None:
    if coverage_summary.empty or column not in coverage_summary.columns:
        return None
    value = coverage_summary.iloc[0].get(column)
    if pd.isna(value):
        return None
    return float(value)


def fmt(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "unavailable"
    return str(value)


def fmt_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "unavailable"
    return f"{float(value):.4f}"


def fmt_bool(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "true" if bool(value) else "false"
