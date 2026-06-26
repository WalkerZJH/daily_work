"""Reusable functions for the BS_Agent_DingDan EDA and cleaning notebook.

The notebook should act as a small main function: configure paths and parameters,
then call functions from this module. Keep data access, profiling, mapping,
desensitization checks, clean table construction, and report generation here.
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
    max_rows: int,
    chunksize: int,
) -> pd.DataFrame:
    if mode == "parquet":
        return pd.read_parquet(paths.raw_parquet_path)
    if mode == "sql_full_to_parquet":
        export_sql_full_to_parquet(
            sql_database_url, sql_table, raw_columns, paths.raw_parquet_path, chunksize
        )
        return pd.read_parquet(paths.raw_parquet_path)
    if mode != "sql_sample":
        raise ValueError(f"Unsupported mode: {mode}")
    if paths.sample_csv_path.exists():
        return pd.read_csv(paths.sample_csv_path)
    return read_sql_sample(sql_database_url, sql_table, raw_columns, max_rows)


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
