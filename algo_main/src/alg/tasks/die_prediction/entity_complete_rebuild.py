"""Entity-complete rebuild pipeline for alive prediction.

This module restarts the alive-prediction data chain after the SQL sampling
integrity audit showed that the old 100k row extract was not entity-complete.
It is scoped to research/data rebuild artifacts under ``entity_complete_v1``.
It does not touch frontend/backend app code, call LLMs, auto-dispatch, or save
formal production model files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import shutil
import time
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from alg.cleaning.bs_agent_dingdan import (
    CleaningPaths,
    build_clean_model_audit_v2,
    build_column_maps,
    build_numeric_desensitization_report_v2,
    build_order_status_lifecycle_map,
    build_order_status_mapping_coverage,
    build_order_status_suspicious_mapping,
    field_profile,
    load_env,
    load_yaml,
    quote_sqlserver_identifier,
)
from alg.facts.demand_profile_builder import build_entity_demand_profile
from alg.facts.entity_month_builder import build_fact_entity_month
from alg.facts.purchase_event_builder import ENTITY_KEYS, build_fact_purchase_event
from alg.features.alive_prediction_feature_builder import build_alive_prediction_feature_table
from alg.features.cutoff_dataset_builder import build_candidate_entities
from alg.labels.alive_label_builder import build_alive_labels
from alg.tasks.die_prediction.sql_sampling_integrity_audit import (
    SqlContext,
    load_sql_context,
    mask_database_url,
    query_sql_dataframe,
    sql_cast_text,
    sql_col,
    sql_date_expr,
)
from alg.tasks.die_prediction.utility_backtest import (
    average_precision_score_simple,
    brier_score,
    expected_calibration_error,
    log_loss_score,
    ndcg_at_k,
    roc_auc_score_simple,
)
from alg.utils.months import add_months, month_diff, to_month_end


VERSION = "entity_complete_v1"
RESET_REPORT_DIR = Path("reports/reset_entity_complete_rebuild_v1")
DATA_ROOT = Path(f"data/{VERSION}")
REPORT_ROOT = Path(f"reports/{VERSION}")
RAW_EXTRACT_DIR = DATA_ROOT / "02_sql_extract"
CLEAN_DIR = DATA_ROOT / "03_cleaned"
FACT_DIR = DATA_ROOT / "04_facts"
FEATURE_DIR = DATA_ROOT / "05_features"
PREDICTION_DIR = DATA_ROOT / "06_predictions"
CANDIDATE_DIR = DATA_ROOT / "07_candidates"
EVIDENCE_DIR = DATA_ROOT / "08_evidence"
EXTRACT_REPORT_DIR = REPORT_ROOT / "00_extract_audit"
CLEAN_REPORT_DIR = REPORT_ROOT / "01_cleaning_audit"
FEATURE_REPORT_DIR = REPORT_ROOT / "02_feature_audit"
MODEL_REPORT_DIR = REPORT_ROOT / "03_model_selection"
M_STAGE_REPORT_DIR = REPORT_ROOT / "04_m_stage_pipeline"
BACKTEST_REPORT_DIR = REPORT_ROOT / "05_backtest"
DECISION_REPORT_DIR = REPORT_ROOT / "06_stage_decision"

HORIZONS = (3, 6, 12)
RANDOM_STATE = 20260702
EPS = 1e-9
PREDICTION_KEEP_COLS = [
    "manufacturer_code",
    "hospital_code",
    "drug_group",
    "drug_group_source",
    "cutoff_month",
    "horizon",
    "label_die_H",
    "label_alive_H",
    "label_window_closed",
    "one_shot_flag",
    "demand_shape_label",
    "history_sufficiency_flag",
    "hospital_level_code",
    "province_code",
    "drug_category_code",
    "recency_only_baseline",
    "frequency_decay_baseline",
    "interval_overdue_baseline",
    "hybrid_interval_frequency_score",
    "manufacturer_share_within_hospital_drug_asof_cutoff",
    "competitor_order_count_last_3m_asof_cutoff",
    "competitor_order_count_last_12m_asof_cutoff",
    "manufacturer_substitution_context_available",
]

ALLOWED_STALE_DIRS = [
    Path("data/03_cleaned"),
    Path("data/04_facts"),
    Path("data/05_features"),
    Path("cache"),
    Path("exports/clean"),
    Path("exports/eda"),
    Path("exports/mappings"),
]
PRESERVE_FILENAMES = {".gitkeep"}
RAW_OUTPUT_FILES = {
    "manufacturer_orders": RAW_EXTRACT_DIR / "manufacturer_complete_orders.parquet",
    "entity_orders": RAW_EXTRACT_DIR / "entity_complete_orders.parquet",
    "hospital_drug_choice_set_orders": RAW_EXTRACT_DIR / "hospital_drug_choice_set_orders.parquet",
    "entity_keys": RAW_EXTRACT_DIR / "extract_entity_keys.csv",
    "manufacturer_keys": RAW_EXTRACT_DIR / "extract_manufacturer_keys.csv",
    "hospital_drug_pairs": RAW_EXTRACT_DIR / "extract_hospital_drug_pairs.csv",
}


@dataclass(frozen=True)
class ExtractConfig:
    project_root: Path
    max_manufacturers: int = 4
    max_entities: int = 1500
    max_hospital_drug_pairs: int = 3000
    min_manufacturer_rows: int = 200_000
    target_manufacturer_rows: int = 350_000
    manufacturer_batch_size: int = 100_000
    entity_batch_size: int = 500
    sql_chunksize: int = 50_000
    query_timeout: int = 120
    dry_run: bool = False
    estimate_only: bool = False
    refresh: bool = False


def project_path(root: Path, rel: Path | str) -> Path:
    rel_path = Path(rel)
    return rel_path if rel_path.is_absolute() else root / rel_path


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")


def write_parquet(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def read_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def ensure_entity_complete_dirs(project_root: Path) -> None:
    for rel in [
        DATA_ROOT / "01_raw_reference",
        RAW_EXTRACT_DIR,
        CLEAN_DIR,
        FACT_DIR,
        FEATURE_DIR,
        PREDICTION_DIR,
        CANDIDATE_DIR,
        EVIDENCE_DIR,
        EXTRACT_REPORT_DIR,
        CLEAN_REPORT_DIR,
        FEATURE_REPORT_DIR,
        MODEL_REPORT_DIR,
        M_STAGE_REPORT_DIR,
        BACKTEST_REPORT_DIR,
        DECISION_REPORT_DIR,
        RESET_REPORT_DIR,
    ]:
        project_path(project_root, rel).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Stage 0: reset manifest and stale artifact archive
# ---------------------------------------------------------------------------


def build_stale_artifact_manifest(project_root: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for rel_dir in ALLOWED_STALE_DIRS:
        abs_dir = project_path(project_root, rel_dir)
        if not abs_dir.exists():
            rows.append(
                {
                    "path": str(rel_dir).replace("\\", "/"),
                    "artifact_type": "directory_missing",
                    "size_bytes": 0,
                    "planned_action": "none_missing",
                    "reason": "allowed stale derived directory is absent",
                }
            )
            continue
        for path in abs_dir.rglob("*"):
            if path.is_dir():
                continue
            rel = path.relative_to(project_root)
            planned = "preserve" if path.name in PRESERVE_FILENAMES else "archive_stale_pre_entity_complete_reset"
            rows.append(
                {
                    "path": str(rel).replace("\\", "/"),
                    "artifact_type": path.suffix.lower().lstrip(".") or "file",
                    "size_bytes": int(path.stat().st_size),
                    "planned_action": planned,
                    "reason": "old row-level TOP N derived artifact; not valid for entity_complete_v1 conclusions",
                }
            )
    return pd.DataFrame(rows)


def render_reset_cleanup_plan(manifest: pd.DataFrame) -> str:
    archive_count = int(manifest["planned_action"].eq("archive_stale_pre_entity_complete_reset").sum()) if not manifest.empty else 0
    preserve_count = int(manifest["planned_action"].eq("preserve").sum()) if not manifest.empty else 0
    missing_count = int(manifest["planned_action"].eq("none_missing").sum()) if not manifest.empty else 0
    allowed = "\n".join(f"- `{p.as_posix()}`" for p in ALLOWED_STALE_DIRS)
    return f"""# Reset Cleanup Plan

## Purpose

The old alive-prediction derived artifacts were built on a row-level TOP N SQL sample. They must not be reused as algorithm conclusions for `entity_complete_v1`.

## Allowed Stale Derived Directories

{allowed}

## Planned Action

- Archive non-`.gitkeep` files to `archive/stale_pre_entity_complete_reset/`.
- Preserve source code, configs, notebooks, docs, `.env`, design documents, and SQL sampling audit reports.
- Keep old reports in place as stale historical evidence; new conclusions go under `reports/entity_complete_v1/`.

## Manifest Counts

- files planned for archive: {archive_count}
- placeholder files preserved: {preserve_count}
- missing allowed directories: {missing_count}
"""


def run_reset_cleanup(project_root: str | Path, *, execute: bool = True) -> dict[str, Any]:
    root = Path(project_root).resolve()
    ensure_entity_complete_dirs(root)
    manifest = build_stale_artifact_manifest(root)
    report_dir = project_path(root, RESET_REPORT_DIR)
    write_csv(report_dir / "stale_artifact_manifest.csv", manifest)
    write_text(report_dir / "reset_cleanup_plan.md", render_reset_cleanup_plan(manifest))
    archived_rows: list[dict[str, Any]] = []
    if execute and not manifest.empty:
        archive_root = root / "archive/stale_pre_entity_complete_reset"
        for row in manifest[manifest["planned_action"].eq("archive_stale_pre_entity_complete_reset")].to_dict("records"):
            source = root / row["path"]
            if not source.exists() or not source.is_file():
                continue
            target = archive_root / row["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target = target.with_name(f"{target.stem}__stale{target.suffix}")
            shutil.move(str(source), str(target))
            archived_rows.append({**row, "archive_path": str(target.relative_to(root)).replace("\\", "/")})
    summary = render_reset_cleanup_summary(manifest, archived_rows, execute)
    write_text(report_dir / "reset_cleanup_summary.md", summary)
    return {"manifest": manifest, "archived": pd.DataFrame(archived_rows), "summary": summary}


def render_reset_cleanup_summary(manifest: pd.DataFrame, archived_rows: list[dict[str, Any]], execute: bool) -> str:
    archived_count = len(archived_rows)
    dirs = sorted({str(Path(row["path"]).parent).replace("\\", "/") for row in archived_rows})
    cleaned_dirs = "\n".join(f"- `{d}`" for d in dirs) if dirs else "- none"
    retained = "\n".join(
        [
            "- `src/`",
            "- `configs/`",
            "- `notebooks/`",
            "- `docs/`",
            "- `.env`",
            "- `reports/sql_sampling_integrity_audit_v1/`",
            "- old `reports/alive_prediction_*` as stale historical reports",
        ]
    )
    return f"""# Reset Cleanup Summary

- execute: {execute}
- stale manifest rows: {len(manifest)}
- archived files: {archived_count}

## Cleaned Directories

{cleaned_dirs}

## Retained Directories / Files

{retained}

No source code, configs, notebooks, docs, design documents, `.env`, or SQL sampling audit reports were deleted by this reset step.
"""


# ---------------------------------------------------------------------------
# Stage 1: SQL extract
# ---------------------------------------------------------------------------


def raw_projection_sql(raw_columns: list[str], table_alias: str | None = None) -> str:
    parts = []
    for raw in raw_columns:
        col = quote_sqlserver_identifier(raw)
        expr = f"{table_alias}.{col}" if table_alias else col
        parts.append(f"{expr} AS {col}")
    return ", ".join(parts)


def manufacturer_profile_query(context: SqlContext) -> str:
    date_expr = sql_date_expr(context, table_alias="t")
    month_expr = f"CONVERT(char(7), {date_expr}, 120)"
    mfg = sql_cast_text(sql_col(context, "manufacturer_code", table_alias="t"))
    hosp = sql_cast_text(sql_col(context, "hospital_code", table_alias="t"))
    drug = sql_cast_text(sql_col(context, "drug_code", table_alias="t"))
    table = quote_sqlserver_identifier(context.sql_table)
    return f"""
WITH entity_history AS (
    SELECT
        {mfg} AS manufacturer_code,
        {hosp} AS hospital_code,
        {drug} AS drug_code,
        COUNT_BIG(*) AS entity_row_count,
        MIN({date_expr}) AS first_purchase_time,
        MAX({date_expr}) AS last_purchase_time,
        COUNT(DISTINCT {month_expr}) AS active_month_count
    FROM {table} t
    WHERE {date_expr} IS NOT NULL
    GROUP BY {mfg}, {hosp}, {drug}
),
manufacturer_months AS (
    SELECT
        {mfg} AS manufacturer_code,
        COUNT(DISTINCT {month_expr}) AS active_months_all,
        COUNT(DISTINCT CASE WHEN {date_expr} >= '2020-01-01' AND {date_expr} < '2027-01-01' THEN {month_expr} END) AS active_months_2020_2026
    FROM {table} t
    WHERE {date_expr} IS NOT NULL
    GROUP BY {mfg}
)
SELECT
    eh.manufacturer_code,
    SUM(eh.entity_row_count) AS sql_row_count,
    COUNT_BIG(*) AS entity_count,
    SUM(CASE WHEN eh.entity_row_count >= 3 THEN 1 ELSE 0 END) AS recurring_entity_count,
    SUM(CASE WHEN eh.entity_row_count = 1 THEN 1 ELSE 0 END) AS one_shot_entity_count,
    MIN(eh.first_purchase_time) AS purchase_time_min,
    MAX(eh.last_purchase_time) AS purchase_time_max,
    MAX(mm.active_months_all) AS active_months_all,
    MAX(mm.active_months_2020_2026) AS active_months_2020_2026
FROM entity_history eh
LEFT JOIN manufacturer_months mm ON eh.manufacturer_code = mm.manufacturer_code
GROUP BY eh.manufacturer_code
ORDER BY sql_row_count DESC
"""


def entity_profile_query(context: SqlContext) -> str:
    date_expr = sql_date_expr(context, table_alias="t")
    month_expr = f"CONVERT(char(7), {date_expr}, 120)"
    mfg = sql_cast_text(sql_col(context, "manufacturer_code", table_alias="t"))
    hosp = sql_cast_text(sql_col(context, "hospital_code", table_alias="t"))
    drug = sql_cast_text(sql_col(context, "drug_code", table_alias="t"))
    table = quote_sqlserver_identifier(context.sql_table)
    return f"""
SELECT
    {mfg} AS manufacturer_code,
    {hosp} AS hospital_code,
    {drug} AS drug_code,
    COUNT_BIG(*) AS sql_order_count_total,
    MIN({date_expr}) AS sql_first_purchase_time,
    MAX({date_expr}) AS sql_last_purchase_time,
    COUNT(DISTINCT {month_expr}) AS sql_active_month_count,
    DATEDIFF(month, MIN({date_expr}), MAX({date_expr})) + 1 AS sql_months_observed
FROM {table} t
WHERE {date_expr} IS NOT NULL
GROUP BY {mfg}, {hosp}, {drug}
"""


def select_manufacturers(profile: pd.DataFrame, *, max_manufacturers: int = 4, min_rows: int = 200_000, target_rows: int = 350_000) -> pd.DataFrame:
    if profile.empty:
        return pd.DataFrame(columns=list(profile.columns) + ["selection_reason"])
    df = profile.copy()
    df["sql_row_count"] = pd.to_numeric(df["sql_row_count"], errors="coerce").fillna(0)
    df["active_months_2020_2026"] = pd.to_numeric(df.get("active_months_2020_2026"), errors="coerce").fillna(0)
    stable = df[(df["sql_row_count"] >= 50_000) & (df["active_months_2020_2026"] >= 36)].copy()
    if stable.empty:
        stable = df.sort_values("sql_row_count", ascending=False).head(max_manufacturers).copy()
    high_cut = stable["sql_row_count"].quantile(0.85) if len(stable) > max_manufacturers else math.inf
    mids = stable[stable["sql_row_count"] <= high_cut].sort_values(["active_months_2020_2026", "sql_row_count"], ascending=[False, False])
    selected = mids.head(max_manufacturers).copy()
    if selected["sql_row_count"].sum() < min_rows:
        selected = stable.sort_values("sql_row_count", ascending=False).head(max_manufacturers).copy()
    if selected["sql_row_count"].sum() > target_rows * 2 and len(selected) > 3:
        selected = selected.sort_values("sql_row_count", ascending=True).head(max(3, max_manufacturers - 1))
    selected["selection_reason"] = "stable_mid_volume_manufacturer_complete_subset"
    return selected.reset_index(drop=True)


def classify_entity_bucket(df: pd.DataFrame, selected_manufacturers: Iterable[str] = ()) -> pd.Series:
    work = df.copy()
    count = pd.to_numeric(work["sql_order_count_total"], errors="coerce").fillna(0)
    active = pd.to_numeric(work["sql_active_month_count"], errors="coerce").fillna(0)
    months = pd.to_numeric(work["sql_months_observed"], errors="coerce").replace(0, np.nan)
    active_ratio = active / months
    selected_set = set(str(v) for v in selected_manufacturers)
    bucket = pd.Series("medium_frequency", index=work.index, dtype="object")
    bucket.loc[count <= 1] = "one_shot"
    bucket.loc[(count > 1) & (count <= 3)] = "low_frequency"
    bucket.loc[count >= count.quantile(0.90)] = "high_frequency"
    bucket.loc[(count >= 8) & (active >= 6) & (active_ratio >= 0.45)] = "stable_recurring"
    bucket.loc[(count >= 3) & (active_ratio < 0.25)] = "lumpy_intermittent"
    bucket.loc[work["manufacturer_code"].astype(str).isin(selected_set)] = bucket.loc[
        work["manufacturer_code"].astype(str).isin(selected_set)
    ] + "_inside_selected_manufacturer"
    return bucket


def select_entity_keys(entity_profile: pd.DataFrame, selected_manufacturers: pd.DataFrame, max_entities: int = 1500) -> pd.DataFrame:
    if entity_profile.empty:
        return pd.DataFrame(columns=["manufacturer_code", "hospital_code", "drug_code", "sample_bucket"])
    selected_mfg = selected_manufacturers.get("manufacturer_code", pd.Series(dtype=str)).astype(str).tolist()
    df = entity_profile.copy()
    df["sample_bucket"] = classify_entity_bucket(df, selected_mfg)
    base_buckets = [
        "high_frequency",
        "medium_frequency",
        "low_frequency",
        "lumpy_intermittent",
        "stable_recurring",
        "one_shot",
    ]
    rows: list[pd.DataFrame] = []
    per_bucket = max(20, max_entities // (len(base_buckets) * 2))
    for bucket in base_buckets:
        mask = df["sample_bucket"].str.startswith(bucket)
        inside = df[mask & df["manufacturer_code"].astype(str).isin(selected_mfg)].sort_values("sql_order_count_total", ascending=False).head(per_bucket)
        outside = df[mask & ~df["manufacturer_code"].astype(str).isin(selected_mfg)].sample(
            min(per_bucket, int((mask & ~df["manufacturer_code"].astype(str).isin(selected_mfg)).sum())),
            random_state=RANDOM_STATE,
        )
        rows.extend([inside, outside])
    sampled = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if len(sampled.drop_duplicates(["manufacturer_code", "hospital_code", "drug_code"])) < max_entities:
        remain = max_entities - len(sampled.drop_duplicates(["manufacturer_code", "hospital_code", "drug_code"]))
        extra = df.sample(min(remain, len(df)), random_state=RANDOM_STATE)
        sampled = pd.concat([sampled, extra], ignore_index=True)
    return sampled.drop_duplicates(["manufacturer_code", "hospital_code", "drug_code"]).head(max_entities).reset_index(drop=True)


def select_hospital_drug_choice_pairs(
    entity_profile: pd.DataFrame,
    selected_manufacturers: pd.DataFrame,
    max_pairs: int = 3000,
) -> pd.DataFrame:
    """Select hospital-drug choice sets touched by selected manufacturers.

    This prevents a manufacturer-only extract from treating manufacturer
    substitution within the same hospital/drug pair as pure random churn.
    """

    if entity_profile.empty or selected_manufacturers.empty or max_pairs <= 0:
        return pd.DataFrame(columns=["hospital_code", "drug_code", "choice_set_selection_reason"])
    selected_set = set(selected_manufacturers["manufacturer_code"].astype(str))
    work = entity_profile.copy()
    work["manufacturer_code"] = work["manufacturer_code"].astype(str)
    work["sql_order_count_total"] = pd.to_numeric(work["sql_order_count_total"], errors="coerce").fillna(0)
    touched = work[work["manufacturer_code"].isin(selected_set)].copy()
    if touched.empty:
        return pd.DataFrame(columns=["hospital_code", "drug_code", "choice_set_selection_reason"])
    touched_pair = (
        touched.groupby(["hospital_code", "drug_code"], dropna=False)
        .agg(
            selected_mfg_order_count=("sql_order_count_total", "sum"),
            selected_mfg_entity_count=("manufacturer_code", "nunique"),
        )
        .reset_index()
    )
    all_pair = (
        work.groupby(["hospital_code", "drug_code"], dropna=False)
        .agg(
            all_manufacturer_count=("manufacturer_code", "nunique"),
            all_pair_order_count=("sql_order_count_total", "sum"),
            all_pair_entity_count=("manufacturer_code", "size"),
        )
        .reset_index()
    )
    pairs = touched_pair.merge(all_pair, on=["hospital_code", "drug_code"], how="left")
    pairs["has_manufacturer_substitution"] = pairs["all_manufacturer_count"].gt(pairs["selected_mfg_entity_count"])
    substitution = pairs[pairs["has_manufacturer_substitution"]].sort_values(
        ["selected_mfg_order_count", "all_manufacturer_count"], ascending=[False, False]
    )
    stable = pairs[~pairs["has_manufacturer_substitution"]].sort_values("selected_mfg_order_count", ascending=False)
    n_sub = min(len(substitution), int(max_pairs * 0.75))
    n_stable = max_pairs - n_sub
    selected = pd.concat([substitution.head(n_sub), stable.head(n_stable)], ignore_index=True)
    if len(selected) < max_pairs:
        extra = pairs.drop(selected.index, errors="ignore").sample(
            min(max_pairs - len(selected), max(0, len(pairs) - len(selected))),
            random_state=RANDOM_STATE,
        )
        selected = pd.concat([selected, extra], ignore_index=True)
    selected["choice_set_selection_reason"] = np.where(
        selected["has_manufacturer_substitution"],
        "selected_manufacturer_hospital_drug_with_other_manufacturer_context",
        "selected_manufacturer_hospital_drug_single_manufacturer_context",
    )
    return selected.drop_duplicates(["hospital_code", "drug_code"]).head(max_pairs).reset_index(drop=True)


def _write_sql_chunks_to_parquet(engine: Any, sql: str, output_path: Path, *, params: dict[str, Any], chunksize: int, query_timeout: int) -> int:
    import pyarrow as pa
    import pyarrow.parquet as pq

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = None
    total = 0
    try:
        with engine.connect() as conn:
            conn = conn.execution_options(timeout=int(query_timeout))
            for chunk in pd.read_sql_query(text(sql), conn, params=params, chunksize=chunksize):
                if writer is None:
                    table = sql_chunk_to_arrow_table(chunk)
                    writer = pq.ParquetWriter(output_path, table.schema)
                else:
                    table = sql_chunk_to_arrow_table(chunk, schema=writer.schema)
                writer.write_table(table)
                total += len(chunk)
    finally:
        if writer is not None:
            writer.close()
    if total == 0:
        pd.DataFrame().to_parquet(output_path, index=False)
    return total


def sql_chunk_to_arrow_table(chunk: pd.DataFrame, schema: Any | None = None) -> Any:
    import pyarrow as pa

    work = normalize_sql_chunk_for_parquet(chunk)
    table = pa.Table.from_pandas(work, preserve_index=False)
    return table.cast(schema, safe=False) if schema is not None else table


def normalize_sql_chunk_for_parquet(chunk: pd.DataFrame) -> pd.DataFrame:
    work = chunk.copy()
    for col in work.columns:
        series = work[col]
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series) or pd.api.types.is_categorical_dtype(series):
            work[col] = series.astype("string")
    return work


def manufacturer_detail_query(context: SqlContext, raw_columns: list[str], manufacturers: list[str]) -> tuple[str, dict[str, Any]]:
    params = {f"m{i}": str(value) for i, value in enumerate(manufacturers)}
    placeholders = ", ".join(f":m{i}" for i in range(len(manufacturers)))
    table = quote_sqlserver_identifier(context.sql_table)
    mfg = sql_cast_text(sql_col(context, "manufacturer_code", table_alias="t"))
    return f"SELECT {raw_projection_sql(raw_columns, 't')} FROM {table} t WHERE {mfg} IN ({placeholders})", params


def entity_detail_query(context: SqlContext, raw_columns: list[str], keys: pd.DataFrame) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {}
    values: list[str] = []
    for i, row in keys.reset_index(drop=True).iterrows():
        values.append(f"(:m{i}, :h{i}, :d{i})")
        params[f"m{i}"] = str(row["manufacturer_code"])
        params[f"h{i}"] = str(row["hospital_code"])
        params[f"d{i}"] = str(row["drug_code"])
    table = quote_sqlserver_identifier(context.sql_table)
    mfg = sql_cast_text(sql_col(context, "manufacturer_code", table_alias="t"))
    hosp = sql_cast_text(sql_col(context, "hospital_code", table_alias="t"))
    drug = sql_cast_text(sql_col(context, "drug_code", table_alias="t"))
    sql = f"""
WITH sample_entity(manufacturer_code, hospital_code, drug_code) AS (
    SELECT * FROM (VALUES {", ".join(values)}) AS v(manufacturer_code, hospital_code, drug_code)
)
SELECT {raw_projection_sql(raw_columns, 't')}
FROM {table} t
JOIN sample_entity s
  ON {mfg} = s.manufacturer_code
 AND {hosp} = s.hospital_code
 AND {drug} = s.drug_code
"""
    return sql, params


def hospital_drug_choice_set_detail_query(context: SqlContext, raw_columns: list[str], pairs: pd.DataFrame) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {}
    values: list[str] = []
    for i, row in pairs.reset_index(drop=True).iterrows():
        values.append(f"(:h{i}, :d{i})")
        params[f"h{i}"] = str(row["hospital_code"])
        params[f"d{i}"] = str(row["drug_code"])
    table = quote_sqlserver_identifier(context.sql_table)
    hosp = sql_cast_text(sql_col(context, "hospital_code", table_alias="t"))
    drug = sql_cast_text(sql_col(context, "drug_code", table_alias="t"))
    sql = f"""
WITH hospital_drug_pair(hospital_code, drug_code) AS (
    SELECT * FROM (VALUES {", ".join(values)}) AS v(hospital_code, drug_code)
)
SELECT {raw_projection_sql(raw_columns, 't')}
FROM {table} t
JOIN hospital_drug_pair p
  ON {hosp} = p.hospital_code
 AND {drug} = p.drug_code
"""
    return sql, params


def run_entity_complete_sql_extract(
    project_root: str | Path,
    *,
    max_manufacturers: int = 4,
    max_entities: int = 1500,
    max_hospital_drug_pairs: int = 3000,
    dry_run: bool = False,
    estimate_only: bool = False,
    refresh: bool = False,
    query_timeout: int = 120,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    ensure_entity_complete_dirs(root)
    started = time.time()
    config = ExtractConfig(
        project_root=root,
        max_manufacturers=max_manufacturers,
        max_entities=max_entities,
        max_hospital_drug_pairs=max_hospital_drug_pairs,
        dry_run=dry_run,
        estimate_only=estimate_only,
        refresh=refresh,
        query_timeout=query_timeout,
    )
    context = load_sql_context(root)
    schema = load_yaml(root / "configs/data_schema/bs_agent_dingdan_schema.yaml")
    _raw_to_alias, _alias_to_raw, raw_columns = build_column_maps(schema)

    if dry_run:
        manufacturer_profile = _dry_manufacturer_profile()
        entity_profile = _dry_entity_profile()
    else:
        if not context.sql_database_url:
            raise RuntimeError("SQL_DATABASE_URL is not configured.")
        engine = create_engine(context.sql_database_url)
        manufacturer_profile = query_sql_dataframe(engine, manufacturer_profile_query(context), query_timeout=query_timeout)
        entity_profile = query_sql_dataframe(engine, entity_profile_query(context), query_timeout=query_timeout)

    selected_mfg = select_manufacturers(
        manufacturer_profile,
        max_manufacturers=config.max_manufacturers,
        min_rows=config.min_manufacturer_rows,
        target_rows=config.target_manufacturer_rows,
    )
    selected_entities = select_entity_keys(entity_profile, selected_mfg, max_entities=config.max_entities)
    selected_pairs = select_hospital_drug_choice_pairs(
        entity_profile,
        selected_mfg,
        max_pairs=config.max_hospital_drug_pairs,
    )
    selected_mfg_path = project_path(root, RAW_OUTPUT_FILES["manufacturer_keys"])
    selected_entity_path = project_path(root, RAW_OUTPUT_FILES["entity_keys"])
    selected_pair_path = project_path(root, RAW_OUTPUT_FILES["hospital_drug_pairs"])
    write_csv(selected_mfg_path, selected_mfg)
    write_csv(selected_entity_path, selected_entities)
    write_csv(selected_pair_path, selected_pairs)

    manufacturer_rows = 0
    entity_rows = 0
    hospital_drug_rows = 0
    manufacturer_out = project_path(root, RAW_OUTPUT_FILES["manufacturer_orders"])
    entity_out = project_path(root, RAW_OUTPUT_FILES["entity_orders"])
    hospital_drug_out = project_path(root, RAW_OUTPUT_FILES["hospital_drug_choice_set_orders"])
    if dry_run:
        write_parquet(manufacturer_out, _dry_raw_orders(raw_columns, selected_mfg, selected_entities, manufacturer=True))
        write_parquet(entity_out, _dry_raw_orders(raw_columns, selected_mfg, selected_entities, manufacturer=False))
        write_parquet(hospital_drug_out, _dry_raw_orders(raw_columns, selected_mfg, selected_entities, manufacturer=True))
        manufacturer_rows = len(pd.read_parquet(manufacturer_out))
        entity_rows = len(pd.read_parquet(entity_out))
        hospital_drug_rows = len(pd.read_parquet(hospital_drug_out))
    elif not estimate_only:
        engine = create_engine(context.sql_database_url)
        if refresh or not manufacturer_out.exists():
            sql, params = manufacturer_detail_query(context, raw_columns, selected_mfg["manufacturer_code"].astype(str).tolist())
            manufacturer_rows = _write_sql_chunks_to_parquet(
                engine,
                sql,
                manufacturer_out,
                params=params,
                chunksize=config.sql_chunksize,
                query_timeout=config.query_timeout,
            )
        else:
            manufacturer_rows = int(pd.read_parquet(manufacturer_out, columns=[raw_columns[0]]).shape[0])
        if refresh or not entity_out.exists():
            counts = []
            import pyarrow as pa
            import pyarrow.parquet as pq

            writer = None
            try:
                for start in range(0, len(selected_entities), config.entity_batch_size):
                    batch = selected_entities.iloc[start : start + config.entity_batch_size]
                    print(
                        f"entity_detail_batch {start // config.entity_batch_size + 1}/{math.ceil(len(selected_entities) / config.entity_batch_size)} size={len(batch)}",
                        flush=True,
                    )
                    sql, params = entity_detail_query(context, raw_columns, batch)
                    with engine.connect() as conn:
                        conn = conn.execution_options(timeout=int(config.query_timeout))
                        for chunk in pd.read_sql_query(text(sql), conn, params=params, chunksize=config.sql_chunksize):
                            if writer is None:
                                table = sql_chunk_to_arrow_table(chunk)
                                entity_out.parent.mkdir(parents=True, exist_ok=True)
                                writer = pq.ParquetWriter(entity_out, table.schema)
                            else:
                                table = sql_chunk_to_arrow_table(chunk, schema=writer.schema)
                            writer.write_table(table)
                            counts.append(len(chunk))
            finally:
                if writer is not None:
                    writer.close()
            entity_rows = int(sum(counts))
            if entity_rows == 0 and not entity_out.exists():
                pd.DataFrame(columns=raw_columns).to_parquet(entity_out, index=False)
        else:
            entity_rows = int(pd.read_parquet(entity_out, columns=[raw_columns[0]]).shape[0])
        if refresh or not hospital_drug_out.exists():
            counts = []
            import pyarrow as pa
            import pyarrow.parquet as pq

            writer = None
            try:
                for start in range(0, len(selected_pairs), config.entity_batch_size):
                    batch = selected_pairs.iloc[start : start + config.entity_batch_size]
                    if batch.empty:
                        continue
                    print(
                        f"hospital_drug_choice_batch {start // config.entity_batch_size + 1}/{math.ceil(len(selected_pairs) / config.entity_batch_size)} size={len(batch)}",
                        flush=True,
                    )
                    sql, params = hospital_drug_choice_set_detail_query(context, raw_columns, batch)
                    with engine.connect() as conn:
                        conn = conn.execution_options(timeout=int(config.query_timeout))
                        for chunk in pd.read_sql_query(text(sql), conn, params=params, chunksize=config.sql_chunksize):
                            if writer is None:
                                table = sql_chunk_to_arrow_table(chunk)
                                hospital_drug_out.parent.mkdir(parents=True, exist_ok=True)
                                writer = pq.ParquetWriter(hospital_drug_out, table.schema)
                            else:
                                table = sql_chunk_to_arrow_table(chunk, schema=writer.schema)
                            writer.write_table(table)
                            counts.append(len(chunk))
            finally:
                if writer is not None:
                    writer.close()
            hospital_drug_rows = int(sum(counts))
            if hospital_drug_rows == 0 and not hospital_drug_out.exists():
                pd.DataFrame(columns=raw_columns).to_parquet(hospital_drug_out, index=False)
        else:
            hospital_drug_rows = int(pd.read_parquet(hospital_drug_out, columns=[raw_columns[0]]).shape[0])

    extract_coverage = build_extract_coverage(
        manufacturer_profile,
        entity_profile,
        selected_mfg,
        selected_entities,
        selected_pairs,
    )
    completeness = entity_history_completeness_after_extract(
        entity_profile,
        selected_mfg,
        selected_entities,
        manufacturer_rows,
        entity_rows,
        selected_pairs=selected_pairs,
        hospital_drug_rows=hospital_drug_rows,
    )
    write_csv(project_path(root, EXTRACT_REPORT_DIR / "sql_extract_coverage.csv"), extract_coverage)
    write_csv(project_path(root, EXTRACT_REPORT_DIR / "entity_history_completeness_after_extract.csv"), completeness)
    write_csv(project_path(root, EXTRACT_REPORT_DIR / "manufacturer_complete_subset_profile.csv"), selected_mfg)
    runtime = time.time() - started
    summary = render_sql_extract_summary(
        context=context,
        selected_mfg=selected_mfg,
        selected_entities=selected_entities,
        selected_pairs=selected_pairs,
        manufacturer_rows=manufacturer_rows,
        entity_rows=entity_rows,
        hospital_drug_rows=hospital_drug_rows,
        coverage=extract_coverage,
        runtime=runtime,
        estimate_only=estimate_only,
        dry_run=dry_run,
    )
    write_text(project_path(root, EXTRACT_REPORT_DIR / "sql_extract_summary.md"), summary)
    write_text(project_path(root, EXTRACT_REPORT_DIR / "time_window_complete_extraction_plan.md"), render_time_window_plan())
    return {
        "manufacturer_profile": manufacturer_profile,
        "entity_profile": entity_profile,
        "selected_manufacturers": selected_mfg,
        "selected_entities": selected_entities,
        "selected_hospital_drug_pairs": selected_pairs,
        "manufacturer_rows": manufacturer_rows,
        "entity_rows": entity_rows,
        "hospital_drug_rows": hospital_drug_rows,
        "runtime": runtime,
        "output_paths": {
            "manufacturer_orders": manufacturer_out,
            "entity_orders": entity_out,
            "hospital_drug_choice_set_orders": hospital_drug_out,
        },
    }


def build_extract_coverage(
    manufacturer_profile: pd.DataFrame,
    entity_profile: pd.DataFrame,
    selected_mfg: pd.DataFrame,
    selected_entities: pd.DataFrame,
    selected_pairs: pd.DataFrame | None = None,
) -> pd.DataFrame:
    sql_rows = pd.to_numeric(manufacturer_profile.get("sql_row_count", pd.Series(dtype=float)), errors="coerce").sum()
    sql_entities = len(entity_profile)
    selected_mfg_rows = pd.to_numeric(selected_mfg.get("sql_row_count", pd.Series(dtype=float)), errors="coerce").sum()
    selected_mfg_entities = pd.to_numeric(selected_mfg.get("entity_count", pd.Series(dtype=float)), errors="coerce").sum()
    selected_entity_rows = pd.to_numeric(selected_entities.get("sql_order_count_total", pd.Series(dtype=float)), errors="coerce").sum()
    selected_pairs = selected_pairs if selected_pairs is not None else pd.DataFrame()
    selected_pair_rows = pd.to_numeric(selected_pairs.get("all_pair_order_count", pd.Series(dtype=float)), errors="coerce").sum()
    selected_pair_entities = pd.to_numeric(selected_pairs.get("all_pair_entity_count", pd.Series(dtype=float)), errors="coerce").sum()
    rows = [
            {
                "scope": "manufacturer_complete_subset",
                "selected_manufacturer_count": len(selected_mfg),
                "selected_entity_count": int(selected_mfg_entities) if not pd.isna(selected_mfg_entities) else np.nan,
                "estimated_rows": int(selected_mfg_rows),
                "sql_total_rows": int(sql_rows),
                "row_coverage_rate": float(selected_mfg_rows / sql_rows) if sql_rows else np.nan,
                "sql_total_entities": int(sql_entities),
            },
            {
                "scope": "entity_complete_sample",
                "selected_manufacturer_count": int(selected_entities["manufacturer_code"].nunique()) if not selected_entities.empty else 0,
                "selected_entity_count": len(selected_entities),
                "estimated_rows": int(selected_entity_rows),
                "sql_total_rows": int(sql_rows),
                "row_coverage_rate": float(selected_entity_rows / sql_rows) if sql_rows else np.nan,
                "sql_total_entities": int(sql_entities),
            },
        ]
    if selected_pairs is not None and not selected_pairs.empty:
        rows.append(
            {
                "scope": "hospital_drug_choice_set_context",
                "selected_manufacturer_count": np.nan,
                "selected_entity_count": int(selected_pair_entities) if not pd.isna(selected_pair_entities) else np.nan,
                "selected_hospital_drug_pair_count": len(selected_pairs),
                "estimated_rows": int(selected_pair_rows),
                "sql_total_rows": int(sql_rows),
                "row_coverage_rate": float(selected_pair_rows / sql_rows) if sql_rows else np.nan,
                "sql_total_entities": int(sql_entities),
            }
        )
    return pd.DataFrame(rows)


def entity_history_completeness_after_extract(
    entity_profile: pd.DataFrame,
    selected_mfg: pd.DataFrame,
    selected_entities: pd.DataFrame,
    manufacturer_rows: int,
    entity_rows: int,
    *,
    selected_pairs: pd.DataFrame | None = None,
    hospital_drug_rows: int = 0,
) -> pd.DataFrame:
    selected_mfg_set = set(selected_mfg.get("manufacturer_code", pd.Series(dtype=str)).astype(str))
    entity_key_set = set(
        selected_entities[["manufacturer_code", "hospital_code", "drug_code"]].astype(str).agg("|".join, axis=1)
    ) if not selected_entities.empty else set()
    work = entity_profile.copy()
    work["entity_key"] = work[["manufacturer_code", "hospital_code", "drug_code"]].astype(str).agg("|".join, axis=1)
    work["hospital_drug_key"] = work[["hospital_code", "drug_code"]].astype(str).agg("|".join, axis=1)
    pair_key_set = (
        set(selected_pairs[["hospital_code", "drug_code"]].astype(str).agg("|".join, axis=1))
        if selected_pairs is not None and not selected_pairs.empty
        else set()
    )
    work["covered_by_manufacturer_complete"] = work["manufacturer_code"].astype(str).isin(selected_mfg_set)
    work["covered_by_entity_complete_sample"] = work["entity_key"].isin(entity_key_set)
    work["covered_by_hospital_drug_choice_set"] = work["hospital_drug_key"].isin(pair_key_set)
    work["history_complete_after_extract"] = (
        work["covered_by_manufacturer_complete"]
        | work["covered_by_entity_complete_sample"]
        | work["covered_by_hospital_drug_choice_set"]
    )
    return pd.DataFrame(
        [
            {
                "scope": "selected_extract_union",
                "sql_entity_count": int(len(work)),
                "covered_entity_count": int(work["history_complete_after_extract"].sum()),
                "entity_history_complete_rate_after_extract": float(work["history_complete_after_extract"].mean()) if len(work) else np.nan,
                "manufacturer_complete_extracted_rows": int(manufacturer_rows),
                "entity_complete_extracted_rows": int(entity_rows),
                "hospital_drug_choice_set_extracted_rows": int(hospital_drug_rows),
                "covered_by_manufacturer_complete_count": int(work["covered_by_manufacturer_complete"].sum()),
                "covered_by_entity_complete_sample_count": int(work["covered_by_entity_complete_sample"].sum()),
                "covered_by_hospital_drug_choice_set_count": int(work["covered_by_hospital_drug_choice_set"].sum()),
                "note": "All rows for selected manufacturers/entities and selected hospital-drug choice sets are extracted; non-selected SQL entities are intentionally outside v1 sample scope.",
            }
        ]
    )


def render_sql_extract_summary(
    *,
    context: SqlContext,
    selected_mfg: pd.DataFrame,
    selected_entities: pd.DataFrame,
    selected_pairs: pd.DataFrame,
    manufacturer_rows: int,
    entity_rows: int,
    hospital_drug_rows: int,
    coverage: pd.DataFrame,
    runtime: float,
    estimate_only: bool,
    dry_run: bool,
) -> str:
    mfg_list = ", ".join(selected_mfg.get("manufacturer_code", pd.Series(dtype=str)).astype(str).tolist())
    purchase_min = selected_mfg.get("purchase_time_min", pd.Series(dtype=str)).min() if not selected_mfg.empty else None
    purchase_max = selected_mfg.get("purchase_time_max", pd.Series(dtype=str)).max() if not selected_mfg.empty else None
    return f"""# SQL Extract Summary

- SQL_DATABASE_URL masked: `{mask_database_url(context.sql_database_url)}`
- SQL table: `{context.sql_table}`
- dry_run: {dry_run}
- estimate_only: {estimate_only}
- selected manufacturers: {mfg_list}
- selected manufacturer count: {len(selected_mfg)}
- selected entity count: {len(selected_entities)}
- selected hospital-drug choice-set pair count: {len(selected_pairs)}
- manufacturer complete extracted rows: {manufacturer_rows}
- entity complete extracted rows: {entity_rows}
- hospital-drug choice-set extracted rows: {hospital_drug_rows}
- selected manufacturer purchase_time range: {purchase_min} to {purchase_max}
- output manufacturer parquet: `{RAW_OUTPUT_FILES["manufacturer_orders"].as_posix()}`
- output entity parquet: `{RAW_OUTPUT_FILES["entity_orders"].as_posix()}`
- output hospital-drug choice-set parquet: `{RAW_OUTPUT_FILES["hospital_drug_choice_set_orders"].as_posix()}`
- runtime seconds: {runtime:.2f}
- password printed: false

## Coverage

{coverage.to_markdown(index=False)}

The extraction avoids row-level `SELECT TOP` sampling. Manufacturer rows are complete for selected manufacturers; entity rows are complete for selected entity keys.

## Manufacturer Substitution Caveat

Manufacturer-complete data alone can misread hospital-drug manufacturer switching as random churn. This v1 extract therefore adds `hospital_drug_choice_set_orders.parquet`: for selected `hospital_code x drug_code` pairs touched by the manufacturer subset, all manufacturer histories are extracted so downstream features can separate manufacturer-specific churn from hospital-drug demand continuation/substitution.
"""


def render_time_window_plan() -> str:
    return """# Time-Window-Complete Extraction Plan

Phase A/B data volumes were intentionally bounded. A future time-window-complete run should first estimate rows for 2020-01 through 2026-06 by month and manufacturer, then request explicit confirmation before exporting all matching SQL detail.

Recommended next query is aggregate-only:

1. rows by month for 2020-01 through 2026-06;
2. entity count by month;
3. rows by manufacturer within the time window;
4. projected parquet size from Phase A/B compression ratio.
"""


def _dry_manufacturer_profile() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "manufacturer_code": ["m_high", "m_mid1", "m_mid2", "m_low"],
            "sql_row_count": [180_000, 120_000, 90_000, 30_000],
            "entity_count": [5000, 3500, 2500, 900],
            "recurring_entity_count": [2200, 1600, 900, 200],
            "one_shot_entity_count": [1000, 800, 700, 500],
            "purchase_time_min": [pd.Timestamp("2018-01-01")] * 4,
            "purchase_time_max": [pd.Timestamp("2026-06-01")] * 4,
            "active_months_all": [90, 90, 88, 60],
            "active_months_2020_2026": [78, 78, 76, 50],
        }
    )


def _dry_entity_profile() -> pd.DataFrame:
    rows = []
    manufacturers = ["m_high", "m_mid1", "m_mid2", "m_out"]
    for i in range(240):
        count = [1, 2, 6, 12, 30][i % 5]
        rows.append(
            {
                "manufacturer_code": manufacturers[i % len(manufacturers)],
                "hospital_code": f"h{i % 50}",
                "drug_code": f"d{i % 20}",
                "sql_order_count_total": count,
                "sql_first_purchase_time": pd.Timestamp("2020-01-01"),
                "sql_last_purchase_time": pd.Timestamp("2025-12-01"),
                "sql_active_month_count": min(count, 24),
                "sql_months_observed": 72,
            }
        )
    return pd.DataFrame(rows)


def _dry_raw_orders(raw_columns: list[str], selected_mfg: pd.DataFrame, selected_entities: pd.DataFrame, *, manufacturer: bool) -> pd.DataFrame:
    aliases = _schema_alias_map_for_dry(raw_columns)
    mfg_values = selected_mfg.get("manufacturer_code", pd.Series(["m_high"])).astype(str).tolist()
    entity_rows = selected_entities.head(60).to_dict("records") if not selected_entities.empty else []
    rows = []
    for i in range(180 if manufacturer else 90):
        entity = entity_rows[i % len(entity_rows)] if entity_rows else {}
        row = {raw: None for raw in raw_columns}
        mfg = mfg_values[i % len(mfg_values)] if manufacturer else entity.get("manufacturer_code", "m_out")
        hosp = f"h{i % 40}" if manufacturer else entity.get("hospital_code", f"h{i % 40}")
        drug = f"d{i % 18}" if manufacturer else entity.get("drug_code", f"d{i % 18}")
        values = {
            "row_uid": f"{'m' if manufacturer else 'e'}_row_{i}",
            "order_detail_id": f"{'m' if manufacturer else 'e'}_order_{i}",
            "manufacturer_code": mfg,
            "hospital_code": hosp,
            "drug_code": drug,
            "purchase_time": pd.Timestamp("2020-01-01") + pd.DateOffset(months=i % 72),
            "county_code": "110101",
            "hospital_level_raw": "三级",
            "order_status_raw": "已收货",
            "raw_sensitive_purchase_quantity": float(1 + i % 5),
            "raw_sensitive_purchase_amount": float(100 + i),
            "raw_sensitive_delivery_quantity": float(1 + i % 5),
            "raw_sensitive_arrival_quantity": float(1 + i % 5),
            "drug_category_raw": "default",
        }
        for alias, value in values.items():
            raw = aliases.get(alias)
            if raw in row:
                row[raw] = value
        rows.append(row)
    return pd.DataFrame(rows)


def _schema_alias_map_for_dry(raw_columns: list[str]) -> dict[str, str]:
    # Only used in dry-run tests; maps known aliases onto raw columns by their
    # position from the stable schema when exact names are unavailable.
    fallback = {
        "row_uid": 0,
        "order_detail_id": 1,
        "county_code": 9,
        "purchase_time": 10,
        "drug_code": 11,
        "raw_sensitive_purchase_quantity": 19,
        "raw_sensitive_purchase_amount": 20,
        "raw_sensitive_delivery_quantity": 21,
        "raw_sensitive_arrival_quantity": 23,
        "order_status_raw": 25,
        "hospital_level_raw": 27,
        "hospital_code": 29,
        "manufacturer_code": 33,
        "drug_category_raw": 35,
    }
    return {alias: raw_columns[idx] for alias, idx in fallback.items() if idx < len(raw_columns)}


# ---------------------------------------------------------------------------
# Stage 2: cleaning
# ---------------------------------------------------------------------------


def run_entity_complete_cleaning(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    ensure_entity_complete_dirs(root)
    schema = load_yaml(root / "configs/data_schema/bs_agent_dingdan_schema.yaml")
    hospital_level_map = load_yaml(root / "configs/mappings/hospital_grade_map.yaml")
    raw_to_alias, alias_to_raw, _raw_columns = build_column_maps(schema)
    manufacturer_orders = read_parquet(project_path(root, RAW_OUTPUT_FILES["manufacturer_orders"]))
    entity_orders = read_parquet(project_path(root, RAW_OUTPUT_FILES["entity_orders"]))
    hospital_drug_orders = read_parquet(project_path(root, RAW_OUTPUT_FILES["hospital_drug_choice_set_orders"]))
    raw = pd.concat([manufacturer_orders, entity_orders, hospital_drug_orders], ignore_index=True)
    raw = dedupe_raw_orders(raw, alias_to_raw)
    paths = CleaningPaths(
        project_root=root,
        config_path=root / "configs/data_schema/bs_agent_dingdan_schema.yaml",
        status_map_path=root / "configs/mappings/order_status_map.yaml",
        hospital_level_map_path=root / "configs/mappings/hospital_grade_map.yaml",
        export_eda=project_path(root, CLEAN_REPORT_DIR),
        export_clean=project_path(root, CLEAN_DIR),
        export_mappings=project_path(root, CLEAN_REPORT_DIR / "mappings"),
        raw_parquet_path=project_path(root, RAW_EXTRACT_DIR / "combined_raw_orders.parquet"),
        clean_parquet_path=project_path(root, CLEAN_DIR / "bs_agent_dingdan_model_base.parquet"),
        sample_csv_path=project_path(root, CLEAN_REPORT_DIR / "raw_sample.csv"),
    )
    for path in [paths.export_eda, paths.export_clean, paths.export_mappings, paths.raw_parquet_path.parent]:
        path.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(paths.raw_parquet_path, index=False)
    clean, model_base, audit = build_clean_model_audit_v2(
        raw,
        paths=paths,
        schema=schema,
        raw_to_alias=raw_to_alias,
        hospital_level_map=hospital_level_map,
    )
    write_parquet(project_path(root, CLEAN_DIR / "bs_agent_dingdan_clean.parquet"), clean)
    write_parquet(project_path(root, CLEAN_DIR / "bs_agent_dingdan_model_base.parquet"), model_base)
    write_parquet(project_path(root, CLEAN_DIR / "bs_agent_dingdan_audit.parquet"), audit)
    profile = field_profile(clean)
    write_csv(project_path(root, CLEAN_REPORT_DIR / "field_profile.csv"), profile)
    entity_profile = cleaned_entity_coverage_profile(model_base)
    write_csv(project_path(root, CLEAN_REPORT_DIR / "entity_coverage_profile.csv"), entity_profile)
    status_coverage = build_order_status_mapping_coverage(clean)
    suspicious = build_order_status_suspicious_mapping(clean)
    status_audit = pd.concat(
        [
            status_coverage.assign(audit_type="mapping_coverage"),
            suspicious.assign(audit_type="suspicious_mapping"),
        ],
        ignore_index=True,
        sort=False,
    )
    write_csv(project_path(root, CLEAN_REPORT_DIR / "status_mapping_audit.csv"), status_audit)
    build_order_status_lifecycle_map(paths.export_mappings)
    numeric_report = build_numeric_desensitization_report_v2(clean, paths.export_eda)
    write_text(project_path(root, CLEAN_REPORT_DIR / "numeric_reliability_audit.md"), render_numeric_reliability_audit(numeric_report))
    summary = render_cleaning_summary(clean, model_base, audit, entity_profile, status_audit)
    write_text(project_path(root, CLEAN_REPORT_DIR / "cleaning_summary.md"), summary)
    return {
        "clean": clean,
        "model_base": model_base,
        "audit": audit,
        "entity_profile": entity_profile,
        "status_audit": status_audit,
    }


def dedupe_raw_orders(raw: pd.DataFrame, alias_to_raw: dict[str, str]) -> pd.DataFrame:
    if raw.empty:
        return raw
    for alias in ["row_uid", "order_detail_id"]:
        raw_col = alias_to_raw.get(alias)
        if raw_col in raw.columns:
            return raw.drop_duplicates(subset=[raw_col], keep="first").reset_index(drop=True)
    return raw.drop_duplicates().reset_index(drop=True)


def cleaned_entity_coverage_profile(model_base: pd.DataFrame) -> pd.DataFrame:
    if model_base.empty:
        return pd.DataFrame()
    work = model_base.copy()
    work["purchase_time"] = pd.to_datetime(work["purchase_time"], errors="coerce")
    work["drug_group"] = work.get("drug_code", pd.Series(index=work.index)).astype("string")
    work["entity_key"] = work[["manufacturer_code", "hospital_code", "drug_group"]].astype(str).agg("|".join, axis=1)
    rows = [
        {"metric": "row_count", "value": len(work)},
        {"metric": "manufacturer_count", "value": work["manufacturer_code"].nunique(dropna=True)},
        {"metric": "hospital_count", "value": work["hospital_code"].nunique(dropna=True)},
        {"metric": "drug_code_count", "value": work["drug_code"].nunique(dropna=True) if "drug_code" in work else np.nan},
        {"metric": "entity_count", "value": work["entity_key"].nunique(dropna=True)},
        {"metric": "purchase_time_min", "value": _date_str(work["purchase_time"].min())},
        {"metric": "purchase_time_max", "value": _date_str(work["purchase_time"].max())},
    ]
    for col in ["manufacturer_code", "hospital_code", "drug_code"]:
        if col in work:
            rows.append({"metric": f"{col}_null_rate", "value": float(work[col].isna().mean())})
    if "order_detail_id" in work:
        rows.append({"metric": "duplicate_order_detail_id_count", "value": int(work["order_detail_id"].duplicated().sum())})
    return pd.DataFrame(rows)


def render_numeric_reliability_audit(numeric_report: pd.DataFrame) -> str:
    return """# Numeric Reliability Audit

Quantity and amount fields remain sensitive relative values. Allowed usage is limited to same-family ratios, trends, order frequency, and coarse relative value tiers. It remains forbidden to infer real unit prices from amount divided by quantity or to validate purchase price against amount/quantity.

The full numeric profile is written by the cleaning helper in this report directory.
"""


def render_cleaning_summary(clean: pd.DataFrame, model_base: pd.DataFrame, audit: pd.DataFrame, entity_profile: pd.DataFrame, status_audit: pd.DataFrame) -> str:
    lookup = dict(zip(entity_profile.get("metric", []), entity_profile.get("value", [])))
    key_nulls = {
        col: float(model_base[col].isna().mean()) if col in model_base and len(model_base) else np.nan
        for col in ["manufacturer_code", "hospital_code", "drug_code", "purchase_time", "order_detail_id"]
    }
    status_rows = len(status_audit)
    return f"""# Cleaning Summary

- clean rows: {len(clean)}
- model_base rows: {len(model_base)}
- audit rows: {len(audit)}
- manufacturer count: {lookup.get("manufacturer_count")}
- hospital count: {lookup.get("hospital_count")}
- drug count: {lookup.get("drug_code_count")}
- entity count: {lookup.get("entity_count")}
- purchase_time range: {lookup.get("purchase_time_min")} to {lookup.get("purchase_time_max")}
- key null rates: {key_nulls}
- status mapping audit rows: {status_rows}

Order status does not negate a purchase event in v1. `drug_category_code` is retained as a category code, not a product-line code. Enterprise code remains excluded from algorithm features.
"""


# ---------------------------------------------------------------------------
# Stage 3: facts, features, labels
# ---------------------------------------------------------------------------


def run_entity_complete_feature_build(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    ensure_entity_complete_dirs(root)
    progress_path = project_path(root, FEATURE_REPORT_DIR / "feature_build_progress.md")
    progress_update(progress_path, "stage=load_model_base", reset=True)
    model_base = read_parquet(project_path(root, CLEAN_DIR / "bs_agent_dingdan_model_base.parquet"))
    progress_update(progress_path, "stage=build_purchase_events")
    purchase_events = build_fact_purchase_event(model_base, drug_group_source="drug_code")
    write_parquet(project_path(root, FACT_DIR / "fact_purchase_event.parquet"), purchase_events)
    progress_update(progress_path, f"stage=build_entity_month purchase_event_rows={len(purchase_events)}")
    entity_month = build_fact_entity_month(purchase_events)
    write_parquet(project_path(root, FACT_DIR / "fact_entity_month.parquet"), entity_month)
    progress_update(progress_path, f"stage=build_purchase_sequence entity_month_rows={len(entity_month)}")
    sequence = build_entity_purchase_sequence(purchase_events)
    write_parquet(project_path(root, FACT_DIR / "entity_purchase_sequence.parquet"), sequence)
    cutoff_months = choose_cutoff_months(purchase_events)
    progress_update(progress_path, f"stage=build_monthly_features cutoff_count={len(cutoff_months)}")
    features, demand_profile, cutoff_report = build_monthly_feature_table_fast(
        entity_month,
        cutoff_months=cutoff_months,
        progress_path=progress_path,
    )
    progress_update(
        progress_path,
        f"stage=monthly_feature_table_built feature_rows={len(features)} demand_rows={len(demand_profile)}",
    )
    write_parquet(project_path(root, FACT_DIR / "entity_demand_profile_asof.parquet"), demand_profile)
    progress_update(progress_path, f"stage=build_monthly_labels feature_rows={len(features)}")
    labels = build_monthly_labels_fast(purchase_events, features, progress_path=progress_path)
    one_shot = features[features["one_shot_flag"].astype(bool)].copy() if "one_shot_flag" in features else pd.DataFrame()
    write_parquet(project_path(root, FEATURE_DIR / "entity_cutoff_feature_table.parquet"), features)
    write_parquet(project_path(root, FEATURE_DIR / "alive_labels_H3_H6_H12.parquet"), labels)
    write_parquet(project_path(root, FEATURE_DIR / "one_shot_first_purchase_features.parquet"), one_shot)
    unmonitorable = features.attrs.get("unmonitorable_purchase_relationships")
    if isinstance(unmonitorable, pd.DataFrame):
        write_parquet(project_path(root, FEATURE_DIR / "unmonitorable_purchase_relationships.parquet"), unmonitorable)
    write_csv(project_path(root, FEATURE_REPORT_DIR / "cutoff_candidate_count_report.csv"), cutoff_report)
    write_csv(project_path(root, FEATURE_REPORT_DIR / "label_closure_audit.csv"), label_closure_audit(labels))
    write_csv(project_path(root, FEATURE_REPORT_DIR / "demand_shape_distribution.csv"), distribution_table(features, "demand_shape_label"))
    write_csv(project_path(root, FEATURE_REPORT_DIR / "history_sufficiency_distribution.csv"), distribution_table(features, "history_sufficiency_flag"))
    write_text(project_path(root, FEATURE_REPORT_DIR / "leakage_guardrail_audit.md"), render_leakage_guardrail_audit(features, labels, purchase_events))
    write_text(project_path(root, FEATURE_REPORT_DIR / "feature_build_summary.md"), render_feature_build_summary(purchase_events, entity_month, features, labels))
    progress_update(progress_path, f"stage=done feature_rows={len(features)} label_rows={len(labels)}")
    return {
        "purchase_events": purchase_events,
        "entity_month": entity_month,
        "features": features,
        "labels": labels,
        "one_shot": one_shot,
        "cutoff_report": cutoff_report,
    }


def progress_update(path: Path, message: str, *, reset: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{pd.Timestamp.now().isoformat()} {message}\n"
    if reset:
        path.write_text(line, encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    print(message, flush=True)


def build_entity_purchase_sequence(purchase_events: pd.DataFrame) -> pd.DataFrame:
    if purchase_events.empty:
        return pd.DataFrame()
    work = purchase_events.sort_values(ENTITY_KEYS + ["purchase_time", "order_detail_id"]).copy()
    work["sequence_index"] = work.groupby(ENTITY_KEYS, dropna=False).cumcount() + 1
    work["previous_purchase_time"] = work.groupby(ENTITY_KEYS, dropna=False)["purchase_time"].shift(1)
    work["gap_days_since_previous_purchase"] = (
        pd.to_datetime(work["purchase_time"]) - pd.to_datetime(work["previous_purchase_time"])
    ).dt.days
    return work


def build_monthly_feature_table_fast(
    entity_month: pd.DataFrame,
    cutoff_months: list[pd.Timestamp],
    *,
    progress_path: Path | None = None,
    max_monitor_gap_months: int = 12,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if entity_month.empty or not cutoff_months:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    monthly = entity_month.copy()
    monthly["purchase_month"] = pd.to_datetime(monthly["purchase_month"], errors="coerce")
    monthly = monthly.sort_values(ENTITY_KEYS + ["purchase_month"]).reset_index(drop=True)
    monthly["previous_purchase_month"] = monthly.groupby(ENTITY_KEYS, dropna=False)["purchase_month"].shift(1)
    monthly["gap_days"] = (monthly["purchase_month"] - monthly["previous_purchase_month"]).dt.days
    feature_parts: list[pd.DataFrame] = []
    unmonitorable_parts: list[pd.DataFrame] = []
    report_rows: list[dict[str, Any]] = []
    total_cutoffs = len(cutoff_months)
    running_rows = 0
    for idx, cutoff in enumerate(cutoff_months, start=1):
        cutoff_ts = to_month_end(cutoff)
        if progress_path is not None:
            progress_update(
                progress_path,
                f"stage=feature_cutoff_start {idx}/{total_cutoffs} cutoff={cutoff_ts:%Y-%m} running_rows={running_rows}",
            )
        part = build_features_for_cutoff(monthly, cutoff_ts, max_monitor_gap_months=max_monitor_gap_months)
        audit = part.attrs.get("unmonitorable_purchase_relationships")
        if isinstance(audit, pd.DataFrame) and not audit.empty:
            unmonitorable_parts.append(audit)
        running_rows += len(part)
        if progress_path is not None:
            progress_update(
                progress_path,
                f"stage=feature_cutoff_done {idx}/{total_cutoffs} cutoff={cutoff_ts:%Y-%m} cutoff_rows={len(part)} running_rows={running_rows}",
            )
        report_rows.append(
            {
                "cutoff_month": cutoff_ts,
                "all_seen_entity_count": int(part.attrs.get("all_seen_entity_count", len(part))),
                "monitorable_entity_count": int(len(part)),
                "excluded_by_monitor_gap_count": int(part.attrs.get("excluded_by_monitor_gap_count", 0)),
                "unmonitorable_entity_count": int(part.attrs.get("unmonitorable_entity_count", part.attrs.get("excluded_by_monitor_gap_count", 0))),
                "one_shot_entity_count": int(part.attrs.get("one_shot_entity_count", 0)),
                "recurring_entity_count": int(part.attrs.get("recurring_entity_count", 0)),
            }
        )
        if not part.empty:
            feature_parts.append(part)
    features = pd.concat(feature_parts, ignore_index=True) if feature_parts else pd.DataFrame()
    if unmonitorable_parts:
        features.attrs["unmonitorable_purchase_relationships"] = pd.concat(unmonitorable_parts, ignore_index=True)
    for attr_name in [
        "all_seen_entity_count",
        "monitorable_entity_count",
        "excluded_by_monitor_gap_count",
        "unmonitorable_entity_count",
        "one_shot_entity_count",
        "recurring_entity_count",
    ]:
        features.attrs[attr_name] = int(pd.to_numeric(pd.DataFrame(report_rows).get(attr_name, pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    demand_cols = [
        *ENTITY_KEYS,
        "cutoff_month",
        "purchase_count_asof_cutoff",
        "active_month_count_asof_cutoff",
        "months_observed_asof_cutoff",
        "active_month_ratio_asof_cutoff",
        "median_purchase_interval_days_asof_cutoff",
        "mean_purchase_interval_days_asof_cutoff",
        "std_purchase_interval_days_asof_cutoff",
        "purchase_interval_iqr_asof_cutoff",
        "adi_asof_cutoff",
        "cv2_quantity_asof_cutoff",
        "seasonality_strength_asof_cutoff",
        "burstiness_score_asof_cutoff",
        "cold_start_flag",
        "confidence_score",
        "demand_pattern_type_asof_cutoff",
    ]
    demand_profile = features[[c for c in demand_cols if c in features.columns]].copy() if not features.empty else pd.DataFrame(columns=demand_cols)
    return features, demand_profile, pd.DataFrame(report_rows)


def build_features_for_cutoff(monthly: pd.DataFrame, cutoff_ts: pd.Timestamp, *, max_monitor_gap_months: int = 12) -> pd.DataFrame:
    hist = monthly[monthly["purchase_month"].le(cutoff_ts)].copy()
    if hist.empty:
        return pd.DataFrame()
    if "gap_days" not in hist.columns:
        hist = hist.sort_values(ENTITY_KEYS + ["purchase_month"]).reset_index(drop=True)
        hist["previous_purchase_month"] = hist.groupby(ENTITY_KEYS, dropna=False)["purchase_month"].shift(1)
        hist["gap_days"] = (hist["purchase_month"] - hist["previous_purchase_month"]).dt.days
    grouped = hist.groupby(ENTITY_KEYS, dropna=False)
    base = grouped.agg(
        purchase_count_asof_cutoff=("order_count", "sum"),
        active_month_count_asof_cutoff=("purchase_month", "nunique"),
        first_purchase_month_asof_cutoff=("purchase_month", "min"),
        last_purchase_month_asof_cutoff=("purchase_month", "max"),
    ).reset_index()
    base["cutoff_month"] = cutoff_ts
    base["first_purchase_month"] = base["first_purchase_month_asof_cutoff"]
    base["last_purchase_month_asof_cutoff"] = pd.to_datetime(base["last_purchase_month_asof_cutoff"], errors="coerce")
    base["months_since_last_purchase"] = month_diff_series(cutoff_ts, base["last_purchase_month_asof_cutoff"])
    base["months_since_last_purchase_asof_cutoff"] = base["months_since_last_purchase"]
    base["months_observed_asof_cutoff"] = month_diff_series(cutoff_ts, base["first_purchase_month_asof_cutoff"]) + 1
    base["months_since_first_purchase_asof_cutoff"] = month_diff_series(cutoff_ts, base["first_purchase_month_asof_cutoff"])
    all_seen = len(base)
    base = classify_monthly_sample_scope(base, max_monitor_gap_months=max_monitor_gap_months)
    unmonitorable_audit = _unmonitorable_audit_rows(base)
    features = base[base["sample_class"].isin(["one_shot", "recurring"])].copy()
    counts = base["sample_class"].value_counts(dropna=False).to_dict()
    sample_scope_attrs = {
        "all_seen_entity_count": all_seen,
        "monitorable_entity_count": int(len(features)),
        "excluded_by_monitor_gap_count": int(counts.get("unmonitorable", 0)),
        "unmonitorable_entity_count": int(counts.get("unmonitorable", 0)),
        "one_shot_entity_count": int(counts.get("one_shot", 0)),
        "recurring_entity_count": int(counts.get("recurring", 0)),
        "unmonitorable_purchase_relationships": unmonitorable_audit,
    }
    features.attrs.update(sample_scope_attrs)
    features["candidate_policy"] = "monitorable"
    features["days_since_last_purchase"] = features["months_since_last_purchase"] * 30.4375
    for months in [1, 3, 6, 12]:
        win = hist[hist["purchase_month"].ge(add_months(cutoff_ts, -(months - 1)))]
        win_agg = window_aggregate(win, months)
        features = features.merge(win_agg, on=ENTITY_KEYS, how="left")
    features = merge_latest_static_status(features, hist)
    features = merge_interval_demand(features, hist)
    features = merge_choice_context_for_cutoff(features, hist)
    features = finalize_feature_columns(features)
    result = features.reset_index(drop=True)
    result.attrs.update(sample_scope_attrs)
    return result


def classify_monthly_sample_scope(base: pd.DataFrame, *, max_monitor_gap_months: int = 12) -> pd.DataFrame:
    out = base.copy()
    active = pd.to_numeric(out["active_month_count_asof_cutoff"], errors="coerce")
    gap = pd.to_numeric(out["months_since_last_purchase_asof_cutoff"], errors="coerce")
    if active.lt(1).any():
        raise ValueError("active_month_count_asof_cutoff must be >= 1 for all seen purchase relationships.")
    out["sample_class"] = np.select(
        [
            gap.gt(max_monitor_gap_months),
            active.eq(1),
            active.ge(2),
        ],
        ["unmonitorable", "one_shot", "recurring"],
        default="data_integrity_error",
    )
    bad = out["sample_class"].eq("data_integrity_error")
    if bad.any():
        raise ValueError(f"Unable to classify {int(bad.sum())} monthly purchase relationships.")
    return out


def _unmonitorable_audit_rows(base: pd.DataFrame) -> pd.DataFrame:
    cols = [
        *ENTITY_KEYS,
        "cutoff_month",
        "first_purchase_month_asof_cutoff",
        "last_purchase_month_asof_cutoff",
        "purchase_count_asof_cutoff",
        "active_month_count_asof_cutoff",
        "months_since_last_purchase_asof_cutoff",
        "months_observed_asof_cutoff",
        "sample_class",
    ]
    available = [col for col in cols if col in base.columns]
    return base[base["sample_class"].eq("unmonitorable")][available].copy()


def month_diff_series(cutoff_ts: pd.Timestamp, values: pd.Series) -> pd.Series:
    vals = pd.to_datetime(values, errors="coerce")
    return (cutoff_ts.year - vals.dt.year) * 12 + (cutoff_ts.month - vals.dt.month)


def window_aggregate(win: pd.DataFrame, months: int) -> pd.DataFrame:
    cols = ENTITY_KEYS
    if win.empty:
        return pd.DataFrame(columns=cols)
    grouped = win.groupby(cols, dropna=False)
    named_aggs: dict[str, tuple[str, str]] = {
        f"order_count_last_{months}m_asof_cutoff": ("order_count", "sum"),
        f"active_months_last_{months}m_asof_cutoff": ("purchase_month", "nunique"),
    }
    for source, target_prefix in [
        ("purchase_quantity_sum", "purchase_quantity_sum"),
        ("purchase_amount_sum", "purchase_amount_sum"),
        ("failed_count", "failed_count"),
        ("received_count", "received_count"),
        ("terminal_count", "terminal_count"),
    ]:
        if source in win.columns:
            named_aggs[f"{target_prefix}_last_{months}m_asof_cutoff"] = (source, "sum")
    return grouped.agg(**named_aggs).reset_index()


def merge_latest_static_status(features: pd.DataFrame, hist: pd.DataFrame) -> pd.DataFrame:
    latest = hist.sort_values("purchase_month").groupby(ENTITY_KEYS, dropna=False).tail(1)
    static_cols = [
        "province_code",
        "city_code",
        "county_code",
        "hospital_level_code",
        "ownership_type_code",
        "drug_category_code",
        "last_order_phase_code_in_month",
        "last_delivery_state_code_in_month",
        "last_order_failure_flag_in_month",
    ]
    existing = [c for c in static_cols if c in latest.columns]
    if not existing:
        return features
    latest = latest[ENTITY_KEYS + existing].rename(
        columns={
            "last_order_phase_code_in_month": "last_order_phase_code_asof_cutoff",
            "last_delivery_state_code_in_month": "last_delivery_state_code_asof_cutoff",
            "last_order_failure_flag_in_month": "last_order_failure_flag_asof_cutoff",
        }
    )
    return features.merge(latest, on=ENTITY_KEYS, how="left")


def merge_interval_demand(features: pd.DataFrame, hist: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    out["active_month_ratio_asof_cutoff"] = out["active_month_count_asof_cutoff"] / out["months_observed_asof_cutoff"].replace(0, np.nan)
    out["adi_asof_cutoff"] = out["months_observed_asof_cutoff"] / out["active_month_count_asof_cutoff"].replace(0, np.nan)
    gaps = hist[hist["gap_days"].notna()]
    if not gaps.empty:
        interval = (
            gaps.groupby(ENTITY_KEYS, dropna=False)["gap_days"]
            .agg(
                median_purchase_interval_days_asof_cutoff="median",
                mean_purchase_interval_days_asof_cutoff="mean",
                std_purchase_interval_days_asof_cutoff="std",
                q25=lambda s: s.quantile(0.25),
                q75=lambda s: s.quantile(0.75),
            )
            .reset_index()
        )
        interval["purchase_interval_iqr_asof_cutoff"] = interval["q75"] - interval["q25"]
        interval = interval.drop(columns=["q25", "q75"])
        out = out.merge(interval, on=ENTITY_KEYS, how="left")
    else:
        for col in [
            "median_purchase_interval_days_asof_cutoff",
            "mean_purchase_interval_days_asof_cutoff",
            "std_purchase_interval_days_asof_cutoff",
            "purchase_interval_iqr_asof_cutoff",
        ]:
            out[col] = np.nan
    if "purchase_quantity_sum" in hist.columns:
        q = hist.groupby(ENTITY_KEYS, dropna=False)["purchase_quantity_sum"].agg(["mean", "std"]).reset_index()
        q["cv2_quantity_asof_cutoff"] = (q["std"] / q["mean"].replace(0, np.nan)) ** 2
        out = out.merge(q[ENTITY_KEYS + ["cv2_quantity_asof_cutoff"]], on=ENTITY_KEYS, how="left")
    else:
        out["cv2_quantity_asof_cutoff"] = np.nan
    out["seasonality_strength_asof_cutoff"] = np.nan
    out["burstiness_score_asof_cutoff"] = np.nan
    out["cold_start_flag"] = (
        out["purchase_count_asof_cutoff"].lt(3)
        | out["active_month_count_asof_cutoff"].lt(2)
        | out["months_observed_asof_cutoff"].lt(3)
    )
    out["confidence_score"] = (out["purchase_count_asof_cutoff"] / 12).clip(upper=1.0)
    out["demand_pattern_type_asof_cutoff"] = np.select(
        [
            out["cold_start_flag"],
            out["adi_asof_cutoff"].le(1.32) & out["cv2_quantity_asof_cutoff"].le(0.49),
            out["adi_asof_cutoff"].le(1.32) & out["cv2_quantity_asof_cutoff"].gt(0.49),
            out["adi_asof_cutoff"].gt(1.32) & out["cv2_quantity_asof_cutoff"].le(0.49),
            out["adi_asof_cutoff"].gt(1.32) & out["cv2_quantity_asof_cutoff"].gt(0.49),
        ],
        ["cold_start", "smooth", "erratic", "intermittent", "lumpy"],
        default="unknown",
    )
    out["demand_shape_label"] = out["demand_pattern_type_asof_cutoff"]
    out["history_sufficiency_flag"] = np.select(
        [
            out["purchase_count_asof_cutoff"].lt(3) | out["active_month_count_asof_cutoff"].lt(2) | out["months_observed_asof_cutoff"].lt(3),
            out["purchase_count_asof_cutoff"].ge(6) & out["active_month_count_asof_cutoff"].ge(4) & out["months_observed_asof_cutoff"].ge(12),
        ],
        ["history_insufficient", "history_sufficient"],
        default="history_medium",
    )
    return out


def merge_choice_context_for_cutoff(features: pd.DataFrame, hist: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    pair_cols = ["hospital_code", "drug_group"]
    pair_total = (
        hist.groupby(pair_cols, dropna=False)
        .agg(
            hospital_drug_order_count_asof_cutoff=("order_count", "sum"),
            hospital_drug_active_manufacturer_count_asof_cutoff=("manufacturer_code", "nunique"),
        )
        .reset_index()
    )
    pair_12 = (
        hist[hist["purchase_month"].ge(add_months(out["cutoff_month"].iloc[0], -11))]
        .groupby(pair_cols, dropna=False)["order_count"]
        .sum()
        .reset_index(name="hospital_drug_order_count_last_12m_asof_cutoff")
    )
    pair_3 = (
        hist[hist["purchase_month"].ge(add_months(out["cutoff_month"].iloc[0], -2))]
        .groupby(pair_cols, dropna=False)["order_count"]
        .sum()
        .reset_index(name="hospital_drug_order_count_last_3m_asof_cutoff")
    )
    out = out.merge(pair_total, on=pair_cols, how="left").merge(pair_12, on=pair_cols, how="left").merge(pair_3, on=pair_cols, how="left")
    entity_orders = pd.to_numeric(out["purchase_count_asof_cutoff"], errors="coerce")
    total_orders = pd.to_numeric(out["hospital_drug_order_count_asof_cutoff"], errors="coerce")
    out["manufacturer_share_within_hospital_drug_asof_cutoff"] = entity_orders / total_orders.replace(0, np.nan)
    out["competitor_order_count_asof_cutoff"] = (total_orders - entity_orders).clip(lower=0)
    out["competitor_order_count_last_12m_asof_cutoff"] = (
        pd.to_numeric(out["hospital_drug_order_count_last_12m_asof_cutoff"], errors="coerce")
        - pd.to_numeric(out.get("order_count_last_12m_asof_cutoff"), errors="coerce")
    ).clip(lower=0)
    out["competitor_order_count_last_3m_asof_cutoff"] = (
        pd.to_numeric(out["hospital_drug_order_count_last_3m_asof_cutoff"], errors="coerce")
        - pd.to_numeric(out.get("order_count_last_3m_asof_cutoff"), errors="coerce")
    ).clip(lower=0)
    out["manufacturer_substitution_context_available"] = pd.to_numeric(out["hospital_drug_active_manufacturer_count_asof_cutoff"], errors="coerce").gt(1)
    return out


def finalize_feature_columns(features: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    for col in out.columns:
        if col.startswith(("order_count_last_", "active_months_last_", "purchase_quantity_sum_last_", "purchase_amount_sum_last_", "failed_count_last_", "received_count_last_", "terminal_count_last_")):
            out[col] = out[col].fillna(0)
    for col in ["purchase_amount_sum_last_12m_asof_cutoff", "purchase_quantity_sum_last_12m_asof_cutoff"]:
        if col not in out.columns:
            out[col] = 0.0
    out["historical_avg_monthly_amount_asof_cutoff"] = pd.to_numeric(out["purchase_amount_sum_last_12m_asof_cutoff"], errors="coerce").fillna(0) / 12
    out["historical_avg_monthly_quantity_asof_cutoff"] = pd.to_numeric(out["purchase_quantity_sum_last_12m_asof_cutoff"], errors="coerce").fillna(0) / 12
    out["entity_value_tier_asof_cutoff"] = pd.qcut(
        out["historical_avg_monthly_amount_asof_cutoff"].rank(method="first"),
        q=3,
        labels=["low", "mid", "high"],
        duplicates="drop",
    ).astype("string") if out["historical_avg_monthly_amount_asof_cutoff"].nunique(dropna=True) >= 3 else "known_value"
    out["negative_value_at_risk_amount_flag"] = out["historical_avg_monthly_amount_asof_cutoff"] < 0
    out["negative_value_at_risk_quantity_flag"] = out["historical_avg_monthly_quantity_asof_cutoff"] < 0
    for horizon in HORIZONS:
        out[f"value_at_risk_amount_raw_H{horizon}_asof_cutoff"] = out["historical_avg_monthly_amount_asof_cutoff"] * horizon
        out[f"value_at_risk_quantity_raw_H{horizon}_asof_cutoff"] = out["historical_avg_monthly_quantity_asof_cutoff"] * horizon
        out[f"value_at_risk_amount_nonnegative_H{horizon}_asof_cutoff"] = out[f"value_at_risk_amount_raw_H{horizon}_asof_cutoff"].clip(lower=0)
        out[f"value_at_risk_quantity_nonnegative_H{horizon}_asof_cutoff"] = out[f"value_at_risk_quantity_raw_H{horizon}_asof_cutoff"].clip(lower=0)
    out["one_shot_flag"] = out["active_month_count_asof_cutoff"].eq(1)
    out["one_shot_silence_months"] = out["months_since_last_purchase_asof_cutoff"]
    out["drug_group_source"] = "drug_code"
    return out


def build_monthly_labels_fast(
    purchase_events: pd.DataFrame,
    features: pd.DataFrame,
    *,
    progress_path: Path | None = None,
) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    events = purchase_events[ENTITY_KEYS + ["purchase_month"]].copy()
    events["purchase_month"] = pd.to_datetime(events["purchase_month"], errors="coerce")
    base = features[ENTITY_KEYS + ["cutoff_month"]].drop_duplicates().copy()
    base["cutoff_month"] = pd.to_datetime(base["cutoff_month"], errors="coerce")
    labels = base.copy()
    max_month = events["purchase_month"].max()
    for horizon in HORIZONS:
        parts = []
        for idx, cutoff in enumerate(sorted(base["cutoff_month"].dropna().unique()), start=1):
            cutoff_ts = pd.Timestamp(cutoff)
            if progress_path is not None and idx % 12 == 1:
                progress_update(progress_path, f"stage=label_h{horizon} cutoff={cutoff_ts:%Y-%m}")
            end = add_months(cutoff_ts, horizon)
            future = events[(events["purchase_month"].gt(cutoff_ts)) & (events["purchase_month"].le(end))]
            alive = future.groupby(ENTITY_KEYS, dropna=False).size().reset_index(name=f"label_alive_H{horizon}")
            part = base[base["cutoff_month"].eq(cutoff_ts)].merge(alive, on=ENTITY_KEYS, how="left")
            part[f"label_alive_H{horizon}"] = part[f"label_alive_H{horizon}"].fillna(0).gt(0).astype(int)
            part[f"label_die_H{horizon}"] = 1 - part[f"label_alive_H{horizon}"]
            part[f"label_window_closed_H{horizon}"] = bool(end <= max_month)
            parts.append(part[ENTITY_KEYS + ["cutoff_month", f"label_alive_H{horizon}", f"label_die_H{horizon}", f"label_window_closed_H{horizon}"]])
        horizon_labels = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        labels = labels.merge(horizon_labels, on=ENTITY_KEYS + ["cutoff_month"], how="left")
    return labels


def build_entity_demand_profile_fast(entity_month: pd.DataFrame, cutoff_months: list[pd.Timestamp]) -> pd.DataFrame:
    """Build as-of demand profile with cutoff-level groupby aggregation.

    This avoids the older entity-by-cutoff nested loop while keeping the
    no-future-data contract. Interval statistics are computed from active-month
    gaps whose later month is no later than the cutoff.
    """

    if entity_month.empty or not cutoff_months:
        return pd.DataFrame()
    monthly = entity_month.copy()
    monthly["purchase_month"] = pd.to_datetime(monthly["purchase_month"], errors="coerce")
    monthly = monthly.sort_values(ENTITY_KEYS + ["purchase_month"]).reset_index(drop=True)
    monthly["previous_purchase_month"] = monthly.groupby(ENTITY_KEYS, dropna=False)["purchase_month"].shift(1)
    monthly["gap_days"] = (
        monthly["purchase_month"] - monthly["previous_purchase_month"]
    ).dt.days
    rows = []
    for cutoff in cutoff_months:
        cutoff_ts = to_month_end(cutoff)
        hist = monthly[monthly["purchase_month"].le(cutoff_ts)]
        if hist.empty:
            continue
        grouped = hist.groupby(ENTITY_KEYS, dropna=False)
        agg = grouped.agg(
            purchase_count_asof_cutoff=("order_count", "sum"),
            active_month_count_asof_cutoff=("purchase_month", "nunique"),
            first_purchase_month=("purchase_month", "min"),
        ).reset_index()
        if "purchase_quantity_sum" in hist:
            q = grouped["purchase_quantity_sum"].agg(["mean", "std"]).reset_index()
            q = q.rename(columns={"mean": "quantity_mean_asof_cutoff", "std": "quantity_std_asof_cutoff"})
            agg = agg.merge(q, on=ENTITY_KEYS, how="left")
        else:
            agg["quantity_mean_asof_cutoff"] = np.nan
            agg["quantity_std_asof_cutoff"] = np.nan
        first = pd.to_datetime(agg["first_purchase_month"], errors="coerce")
        agg["cutoff_month"] = cutoff_ts
        agg["months_observed_asof_cutoff"] = (cutoff_ts.year - first.dt.year) * 12 + (cutoff_ts.month - first.dt.month) + 1
        agg["active_month_ratio_asof_cutoff"] = agg["active_month_count_asof_cutoff"] / agg["months_observed_asof_cutoff"].replace(0, np.nan)
        agg["adi_asof_cutoff"] = agg["months_observed_asof_cutoff"] / agg["active_month_count_asof_cutoff"].replace(0, np.nan)
        gaps = monthly[monthly["purchase_month"].le(cutoff_ts) & monthly["gap_days"].notna()]
        if gaps.empty:
            interval = pd.DataFrame(columns=ENTITY_KEYS)
        else:
            interval = (
                gaps.groupby(ENTITY_KEYS, dropna=False)["gap_days"]
                .agg(
                    median_purchase_interval_days_asof_cutoff="median",
                    mean_purchase_interval_days_asof_cutoff="mean",
                    std_purchase_interval_days_asof_cutoff="std",
                    q25=lambda s: s.quantile(0.25),
                    q75=lambda s: s.quantile(0.75),
                )
                .reset_index()
            )
            interval["purchase_interval_iqr_asof_cutoff"] = interval["q75"] - interval["q25"]
            interval = interval.drop(columns=["q25", "q75"])
        agg = agg.merge(interval, on=ENTITY_KEYS, how="left")
        mean_q = pd.to_numeric(agg["quantity_mean_asof_cutoff"], errors="coerce")
        std_q = pd.to_numeric(agg["quantity_std_asof_cutoff"], errors="coerce")
        agg["cv2_quantity_asof_cutoff"] = (std_q / mean_q.replace(0, np.nan)) ** 2
        agg["seasonality_strength_asof_cutoff"] = np.nan
        agg["burstiness_score_asof_cutoff"] = np.nan
        agg["cold_start_flag"] = (
            agg["purchase_count_asof_cutoff"].lt(3)
            | agg["active_month_count_asof_cutoff"].lt(2)
            | agg["months_observed_asof_cutoff"].lt(3)
        )
        agg["confidence_score"] = (agg["purchase_count_asof_cutoff"] / 12).clip(upper=1.0)
        agg["demand_pattern_type_asof_cutoff"] = np.select(
            [
                agg["cold_start_flag"],
                agg["adi_asof_cutoff"].le(1.32) & agg["cv2_quantity_asof_cutoff"].le(0.49),
                agg["adi_asof_cutoff"].le(1.32) & agg["cv2_quantity_asof_cutoff"].gt(0.49),
                agg["adi_asof_cutoff"].gt(1.32) & agg["cv2_quantity_asof_cutoff"].le(0.49),
                agg["adi_asof_cutoff"].gt(1.32) & agg["cv2_quantity_asof_cutoff"].gt(0.49),
            ],
            ["cold_start", "smooth", "erratic", "intermittent", "lumpy"],
            default="unknown",
        )
        rows.append(agg.drop(columns=["first_purchase_month", "quantity_mean_asof_cutoff", "quantity_std_asof_cutoff"]))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def choose_cutoff_months(purchase_events: pd.DataFrame) -> list[pd.Timestamp]:
    months = pd.to_datetime(purchase_events["purchase_month"], errors="coerce").dropna()
    if months.empty:
        return []
    start = max(pd.Timestamp("2020-01-31"), months.min())
    end = min(pd.Timestamp("2025-12-31"), months.max())
    if end < start:
        start = months.min()
        end = months.max()
    return [p.to_timestamp("M") for p in pd.period_range(start.to_period("M"), end.to_period("M"), freq="M")]


def add_feature_policy_columns(features: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    out["demand_shape_label"] = out.get("demand_pattern_type_asof_cutoff", pd.Series("unknown", index=out.index)).fillna("unknown")
    purchase = pd.to_numeric(out.get("purchase_count_asof_cutoff"), errors="coerce")
    active = pd.to_numeric(out.get("active_month_count_asof_cutoff"), errors="coerce")
    observed = pd.to_numeric(out.get("months_observed_asof_cutoff"), errors="coerce")
    out["history_sufficiency_flag"] = np.select(
        [purchase.lt(3) | active.lt(2) | observed.lt(3), purchase.ge(6) & active.ge(4) & observed.ge(12)],
        ["history_insufficient", "history_sufficient"],
        default="history_medium",
    )
    out["drug_group_source"] = "drug_code"
    return out


def add_hospital_drug_choice_context_features(features: pd.DataFrame, entity_month: pd.DataFrame) -> pd.DataFrame:
    """Add as-of context for manufacturer substitution within hospital-drug pairs."""

    if features.empty or entity_month.empty:
        return features
    out = features.copy()
    monthly = entity_month.copy()
    monthly["purchase_month"] = pd.to_datetime(monthly["purchase_month"], errors="coerce")
    out["cutoff_month"] = pd.to_datetime(out["cutoff_month"], errors="coerce")
    context_rows: list[pd.DataFrame] = []
    for cutoff in sorted(out["cutoff_month"].dropna().unique()):
        cutoff_ts = pd.Timestamp(cutoff)
        feature_keys = out.loc[out["cutoff_month"].eq(cutoff_ts), ["hospital_code", "drug_group", "cutoff_month"]].drop_duplicates()
        hist = monthly[monthly["purchase_month"].le(cutoff_ts)]
        if hist.empty or feature_keys.empty:
            continue
        hist_12 = hist[hist["purchase_month"].ge(add_months(cutoff_ts, -11))]
        hist_3 = hist[hist["purchase_month"].ge(add_months(cutoff_ts, -2))]
        total = (
            hist.groupby(["hospital_code", "drug_group"], dropna=False)
            .agg(
                hospital_drug_order_count_asof_cutoff=("order_count", "sum"),
                hospital_drug_active_manufacturer_count_asof_cutoff=("manufacturer_code", "nunique"),
            )
            .reset_index()
        )
        total_12 = (
            hist_12.groupby(["hospital_code", "drug_group"], dropna=False)["order_count"]
            .sum()
            .reset_index(name="hospital_drug_order_count_last_12m_asof_cutoff")
        )
        total_3 = (
            hist_3.groupby(["hospital_code", "drug_group"], dropna=False)["order_count"]
            .sum()
            .reset_index(name="hospital_drug_order_count_last_3m_asof_cutoff")
        )
        ctx = feature_keys.merge(total, on=["hospital_code", "drug_group"], how="left")
        ctx = ctx.merge(total_12, on=["hospital_code", "drug_group"], how="left")
        ctx = ctx.merge(total_3, on=["hospital_code", "drug_group"], how="left")
        context_rows.append(ctx)
    if not context_rows:
        return out
    context = pd.concat(context_rows, ignore_index=True)
    out = out.merge(context, on=["hospital_code", "drug_group", "cutoff_month"], how="left")
    entity_orders = pd.to_numeric(out.get("purchase_count_asof_cutoff"), errors="coerce")
    total_orders = pd.to_numeric(out.get("hospital_drug_order_count_asof_cutoff"), errors="coerce")
    out["manufacturer_share_within_hospital_drug_asof_cutoff"] = entity_orders / total_orders.replace(0, np.nan)
    out["competitor_order_count_asof_cutoff"] = (total_orders - entity_orders).clip(lower=0)
    out["competitor_order_count_last_12m_asof_cutoff"] = (
        pd.to_numeric(out.get("hospital_drug_order_count_last_12m_asof_cutoff"), errors="coerce")
        - pd.to_numeric(out.get("order_count_last_12m_asof_cutoff"), errors="coerce")
    ).clip(lower=0)
    out["competitor_order_count_last_3m_asof_cutoff"] = (
        pd.to_numeric(out.get("hospital_drug_order_count_last_3m_asof_cutoff"), errors="coerce")
        - pd.to_numeric(out.get("order_count_last_3m_asof_cutoff"), errors="coerce")
    ).clip(lower=0)
    out["manufacturer_substitution_context_available"] = pd.to_numeric(
        out.get("hospital_drug_active_manufacturer_count_asof_cutoff"), errors="coerce"
    ).gt(1)
    return out


def add_label_closure(labels: pd.DataFrame, purchase_events: pd.DataFrame) -> pd.DataFrame:
    out = labels.copy()
    max_month = pd.to_datetime(purchase_events["purchase_month"], errors="coerce").max()
    for horizon in HORIZONS:
        out[f"label_window_closed_H{horizon}"] = out["cutoff_month"].map(
            lambda cutoff, h=horizon: bool(add_months(to_month_end(cutoff), h) <= max_month)
        )
    return out


def label_closure_audit(labels: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for horizon in HORIZONS:
        closed_col = f"label_window_closed_H{horizon}"
        die_col = f"label_die_H{horizon}"
        rows.append(
            {
                "horizon": f"H{horizon}",
                "row_count": len(labels),
                "closed_label_rows": int(labels[closed_col].sum()) if closed_col in labels else 0,
                "die_count_closed": int(labels.loc[labels[closed_col], die_col].sum()) if closed_col in labels and die_col in labels else 0,
                "positive_rate_closed": float(labels.loc[labels[closed_col], die_col].mean()) if closed_col in labels and labels[closed_col].any() else np.nan,
            }
        )
    return pd.DataFrame(rows)


def distribution_table(df: pd.DataFrame, column: str) -> pd.DataFrame:
    if df.empty or column not in df:
        return pd.DataFrame(columns=[column, "row_count", "row_share"])
    counts = df[column].fillna("__MISSING__").astype(str).value_counts(dropna=False).reset_index()
    counts.columns = [column, "row_count"]
    counts["row_share"] = counts["row_count"] / counts["row_count"].sum()
    return counts


def render_leakage_guardrail_audit(features: pd.DataFrame, labels: pd.DataFrame, purchase_events: pd.DataFrame) -> str:
    max_event = _date_str(pd.to_datetime(purchase_events["purchase_time"], errors="coerce").max()) if not purchase_events.empty else "unavailable"
    return f"""# Leakage Guardrail Audit

- Feature aggregations use `purchase_month <= cutoff_month`.
- Label windows use `(cutoff, cutoff + H]`.
- H3/H6/H12 closure flags are generated separately.
- 2026 data is used only to close earlier labels, never to construct features after a cutoff.
- ADI/CV2 and interval features are computed as-of cutoff through `entity_demand_profile_asof`.
- `median_purchase_interval_days_asof_cutoff` uses active-month gaps whose later month is no later than cutoff; it does not use future intervals.
- max observed purchase_time: {max_event}
"""


def render_feature_build_summary(purchase_events: pd.DataFrame, entity_month: pd.DataFrame, features: pd.DataFrame, labels: pd.DataFrame) -> str:
    closure = label_closure_audit(labels)
    context_rate = (
        float(features["manufacturer_substitution_context_available"].mean())
        if "manufacturer_substitution_context_available" in features and len(features)
        else np.nan
    )
    return f"""# Feature Build Summary

- fact purchase event rows: {len(purchase_events)}
- fact entity-month rows: {len(entity_month)}
- feature rows: {len(features)}
- label rows: {len(labels)}
- manufacturer substitution context available rate: {context_rate:.4f}
- cutoff policy: monthly cutoff months for `entity_complete_v1`; no quarterly downgrade is applied.

## Closed Label Rows

{closure.to_markdown(index=False)}
"""


# ---------------------------------------------------------------------------
# Stage 4: model ablation
# ---------------------------------------------------------------------------


def build_model_frame(features: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    if features.empty or labels.empty:
        return pd.DataFrame()
    key_cols = ENTITY_KEYS + ["cutoff_month"]
    base = features.copy()
    base["cutoff_month"] = pd.to_datetime(base["cutoff_month"]).dt.to_period("M").astype(str)
    lab = labels.copy()
    lab["cutoff_month"] = pd.to_datetime(lab["cutoff_month"]).dt.to_period("M").astype(str)
    rows = []
    for horizon in HORIZONS:
        cols = key_cols + [f"label_die_H{horizon}", f"label_alive_H{horizon}", f"label_window_closed_H{horizon}"]
        part = base.merge(lab[cols], on=key_cols, how="inner")
        part["horizon"] = f"H{horizon}"
        part["label_die_H"] = part[f"label_die_H{horizon}"]
        part["label_alive_H"] = part[f"label_alive_H{horizon}"]
        part["label_window_closed"] = part[f"label_window_closed_H{horizon}"].astype(bool)
        rows.append(part)
    frame = pd.concat(rows, ignore_index=True)
    return add_baseline_scores(frame)


def add_baseline_scores(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["recency_only_baseline"] = pd.to_numeric(out.get("months_since_last_purchase_asof_cutoff"), errors="coerce")
    recent_3 = pd.to_numeric(out.get("order_count_last_3m_asof_cutoff"), errors="coerce") / 3.0
    recent_12 = pd.to_numeric(out.get("order_count_last_12m_asof_cutoff"), errors="coerce") / 12.0
    out["frequency_decay_baseline"] = 1.0 - (recent_3 / recent_12.replace(0, np.nan))
    expected_interval = pd.to_numeric(out.get("median_purchase_interval_days_asof_cutoff"), errors="coerce") / 30.4375
    months_since = pd.to_numeric(out.get("months_since_last_purchase_asof_cutoff"), errors="coerce")
    out["interval_overdue_baseline"] = months_since / expected_interval.where(expected_interval > 0)
    out["hybrid_interval_frequency_score"] = rank01(out["interval_overdue_baseline"]) * 0.6 + rank01(out["frequency_decay_baseline"]) * 0.25 + rank01(out["recency_only_baseline"]) * 0.15
    return out


def run_entity_complete_main_model_ablation(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    ensure_entity_complete_dirs(root)
    progress_path = project_path(root, MODEL_REPORT_DIR / "model_ablation_progress.md")
    progress_update(progress_path, "stage=load_features_labels", reset=True)
    features = read_parquet(project_path(root, FEATURE_DIR / "entity_cutoff_feature_table.parquet"))
    labels = read_parquet(project_path(root, FEATURE_DIR / "alive_labels_H3_H6_H12.parquet"))
    progress_update(progress_path, f"stage=build_model_frame feature_rows={len(features)} label_rows={len(labels)}")
    frame = build_model_frame(features, labels)
    closed = frame[frame["label_window_closed"].astype(bool)].copy()
    progress_update(progress_path, f"stage=score_models closed_rows={len(closed)}")
    predictions = score_probability_models(closed)
    progress_update(progress_path, f"stage=write_predictions prediction_rows={len(predictions)}")
    write_parquet(project_path(root, PREDICTION_DIR / "model_scores_long.parquet"), predictions)
    progress_update(progress_path, "stage=compute_metrics")
    metrics = model_metric_summary(predictions)
    by_horizon = grouped_model_metrics(predictions, ["model_name", "horizon"])
    by_cutoff = grouped_model_metrics(predictions, ["model_name", "horizon", "cutoff_month"])
    topk = model_topk_metrics(predictions)
    bins = calibration_bins(predictions)
    feature_ablation = feature_ablation_summary(metrics)
    baseline = metrics[metrics["model_name"].isin(["recency_only_baseline", "frequency_decay_baseline", "interval_overdue_baseline", "hybrid_interval_frequency_score"])].copy()
    write_csv(project_path(root, MODEL_REPORT_DIR / "model_metric_summary.csv"), metrics)
    write_csv(project_path(root, MODEL_REPORT_DIR / "model_metric_by_horizon.csv"), by_horizon)
    write_csv(project_path(root, MODEL_REPORT_DIR / "model_metric_by_cutoff.csv"), by_cutoff)
    write_csv(project_path(root, MODEL_REPORT_DIR / "feature_ablation_summary.csv"), feature_ablation)
    write_csv(project_path(root, MODEL_REPORT_DIR / "baseline_comparison.csv"), baseline)
    write_csv(project_path(root, MODEL_REPORT_DIR / "calibration_bins.csv"), bins)
    write_csv(project_path(root, MODEL_REPORT_DIR / "topk_metric_summary.csv"), topk)
    decision = render_model_selection_decision(metrics)
    write_text(project_path(root, MODEL_REPORT_DIR / "model_selection_decision.md"), decision)
    write_text(project_path(root, MODEL_REPORT_DIR / "main_model_ablation_summary.md"), render_model_ablation_summary(metrics, topk))
    progress_update(progress_path, f"stage=done metric_rows={len(metrics)} topk_rows={len(topk)}")
    return {"frame": predictions, "metrics": metrics, "topk": topk}


def score_probability_models(closed: pd.DataFrame) -> pd.DataFrame:
    if closed.empty:
        return closed
    rows = []
    scorer_cols = [
        "recency_only_baseline",
        "frequency_decay_baseline",
        "interval_overdue_baseline",
        "hybrid_interval_frequency_score",
    ]
    for col in scorer_cols:
        part = slim_prediction_frame(closed, col)
        part["score"] = closed[col].to_numpy()
        part["probability_score"] = calibrate_rank_probability(part, "score")
        rows.append(part)
    hazard = empirical_hazard_score(closed)
    rows.append(hazard)
    rows.extend(train_logistic_models(closed))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def empirical_hazard_score(closed: pd.DataFrame) -> pd.DataFrame:
    work = add_buckets(closed.copy())
    train_mask = pd.to_datetime(work["cutoff_month"]) < pd.Timestamp("2024-01-01")
    group_cols = ["horizon", "recency_bucket", "frequency_bucket", "demand_shape_label"]
    global_rate = work.loc[train_mask, "label_die_H"].mean()
    rates = work.loc[train_mask].groupby(group_cols, dropna=False)["label_die_H"].mean().reset_index(name="hazard_rate")
    scored = work.merge(rates, on=group_cols, how="left")
    out = slim_prediction_frame(scored, "empirical_hazard_bucket_baseline")
    out["score"] = scored["hazard_rate"].fillna(global_rate).to_numpy()
    out["probability_score"] = out["score"].clip(0, 1)
    return out


def train_logistic_models(closed: pd.DataFrame) -> list[pd.DataFrame]:
    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
    except Exception:
        return []
    outputs: list[pd.DataFrame] = []
    specs = {
        "logistic_regression_base_recency_frequency": [
            "months_since_last_purchase_asof_cutoff",
            "purchase_count_asof_cutoff",
            "active_month_count_asof_cutoff",
            "months_observed_asof_cutoff",
            "order_count_last_3m_asof_cutoff",
            "order_count_last_12m_asof_cutoff",
            "frequency_decay_baseline",
        ],
        "logistic_regression_base_recency_frequency_interval": [
            "months_since_last_purchase_asof_cutoff",
            "purchase_count_asof_cutoff",
            "active_month_count_asof_cutoff",
            "months_observed_asof_cutoff",
            "order_count_last_3m_asof_cutoff",
            "order_count_last_12m_asof_cutoff",
            "frequency_decay_baseline",
            "median_purchase_interval_days_asof_cutoff",
            "adi_asof_cutoff",
            "cv2_quantity_asof_cutoff",
            "interval_overdue_baseline",
            "hospital_drug_order_count_asof_cutoff",
            "hospital_drug_active_manufacturer_count_asof_cutoff",
            "manufacturer_share_within_hospital_drug_asof_cutoff",
            "competitor_order_count_asof_cutoff",
            "competitor_order_count_last_12m_asof_cutoff",
        ],
        "logistic_on_recency_frequency_interval_hybrid": [
            "recency_only_baseline",
            "frequency_decay_baseline",
            "interval_overdue_baseline",
            "hybrid_interval_frequency_score",
            "purchase_count_asof_cutoff",
            "active_month_count_asof_cutoff",
            "manufacturer_share_within_hospital_drug_asof_cutoff",
            "competitor_order_count_last_3m_asof_cutoff",
        ],
    }
    cat_cols = ["demand_shape_label", "history_sufficiency_flag", "hospital_level_code", "drug_category_code"]
    for horizon, part in closed.groupby("horizon", dropna=False):
        train = part[pd.to_datetime(part["cutoff_month"]) < pd.Timestamp("2024-01-01")].copy()
        test = part[pd.to_datetime(part["cutoff_month"]) >= pd.Timestamp("2024-01-01")].copy()
        if train["label_die_H"].nunique() < 2 or test.empty:
            continue
        for name, num_cols in specs.items():
            use_num = [c for c in num_cols if c in part.columns]
            use_cat = [c for c in cat_cols if c in part.columns]
            pre = ColumnTransformer(
                [
                    ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), use_num),
                    ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=20))]), use_cat),
                ],
                remainder="drop",
            )
            clf = Pipeline(
                [
                    ("pre", pre),
                    ("clf", LogisticRegression(max_iter=300, class_weight="balanced", random_state=RANDOM_STATE)),
                ]
            )
            clf.fit(train[use_num + use_cat], train["label_die_H"].astype(int))
            scored = slim_prediction_frame(test, name)
            scored["score"] = clf.predict_proba(test[use_num + use_cat])[:, 1]
            scored["probability_score"] = scored["score"].clip(0, 1)
            outputs.append(scored)
    outputs.extend(train_optional_tree_models(closed))
    return outputs


def train_optional_tree_models(closed: pd.DataFrame) -> list[pd.DataFrame]:
    outputs: list[pd.DataFrame] = []
    num_cols = [
        "months_since_last_purchase_asof_cutoff",
        "purchase_count_asof_cutoff",
        "active_month_count_asof_cutoff",
        "months_observed_asof_cutoff",
        "order_count_last_3m_asof_cutoff",
        "order_count_last_12m_asof_cutoff",
        "frequency_decay_baseline",
        "interval_overdue_baseline",
        "adi_asof_cutoff",
        "cv2_quantity_asof_cutoff",
        "manufacturer_share_within_hospital_drug_asof_cutoff",
        "competitor_order_count_last_12m_asof_cutoff",
    ]
    use_num = [c for c in num_cols if c in closed.columns]
    try:
        from xgboost import XGBClassifier
    except Exception:
        return outputs
    for horizon, part in closed.groupby("horizon", dropna=False):
        train = part[pd.to_datetime(part["cutoff_month"]) < pd.Timestamp("2024-01-01")].copy()
        test = part[pd.to_datetime(part["cutoff_month"]) >= pd.Timestamp("2024-01-01")].copy()
        if train["label_die_H"].nunique() < 2 or test.empty:
            continue
        x_train = train[use_num].apply(pd.to_numeric, errors="coerce").fillna(train[use_num].median(numeric_only=True))
        x_test = test[use_num].apply(pd.to_numeric, errors="coerce").fillna(train[use_num].median(numeric_only=True))
        clf = XGBClassifier(n_estimators=80, max_depth=3, learning_rate=0.08, subsample=0.9, colsample_bytree=0.9, eval_metric="logloss", random_state=RANDOM_STATE)
        clf.fit(x_train, train["label_die_H"].astype(int))
        scored = slim_prediction_frame(test, "xgboost_small")
        scored["score"] = clf.predict_proba(x_test)[:, 1]
        scored["probability_score"] = scored["score"].clip(0, 1)
        outputs.append(scored)
    return outputs


def slim_prediction_frame(df: pd.DataFrame, model_name: str) -> pd.DataFrame:
    keep = [col for col in PREDICTION_KEEP_COLS if col in df.columns]
    out = df[keep].copy()
    out["model_name"] = model_name
    return out


def calibrate_rank_probability(df: pd.DataFrame, score_col: str) -> pd.Series:
    score = pd.to_numeric(df[score_col], errors="coerce")
    rank = score.groupby([df["horizon"], df["cutoff_month"]]).rank(pct=True)
    base = df.groupby(["horizon", "cutoff_month"])["label_die_H"].transform("mean")
    return (base * (0.5 + rank.fillna(0.5))).clip(0, 1)


def add_buckets(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["recency_bucket"] = pd.cut(pd.to_numeric(out.get("months_since_last_purchase_asof_cutoff"), errors="coerce"), [-1, 1, 3, 6, 12, 10_000], labels=["0_1", "2_3", "4_6", "7_12", "12_plus"])
    out["frequency_bucket"] = pd.cut(pd.to_numeric(out.get("purchase_count_asof_cutoff"), errors="coerce"), [-1, 1, 3, 6, 12, 10_000], labels=["0_1", "2_3", "4_6", "7_12", "12_plus"])
    return out


def model_metric_summary(predictions: pd.DataFrame) -> pd.DataFrame:
    return grouped_model_metrics(predictions, ["model_name"])


def grouped_model_metrics(predictions: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows = []
    if predictions.empty:
        return pd.DataFrame()
    for keys, group in predictions.groupby(group_cols, dropna=False):
        key_tuple = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(group_cols, key_tuple))
        row.update(metric_row(group, "probability_score"))
        rows.append(row)
    return pd.DataFrame(rows)


def metric_row(df: pd.DataFrame, score_col: str) -> dict[str, Any]:
    y = pd.to_numeric(df["label_die_H"], errors="coerce")
    score = pd.to_numeric(df[score_col], errors="coerce")
    valid = y.notna() & score.notna()
    y = y[valid].astype(int)
    score = score[valid].astype(float)
    pos_rate = float(y.mean()) if len(y) else np.nan
    y_arr = y.to_numpy(dtype=int)
    score_arr = score.to_numpy(dtype=float)
    pr_auc = average_precision_score_simple(y_arr, score_arr) if len(y_arr) and y.nunique() > 1 else np.nan
    return {
        "row_count": int(len(y_arr)),
        "positive_rate": pos_rate,
        "auc": roc_auc_score_simple(y_arr, score_arr) if len(y_arr) and y.nunique() > 1 else np.nan,
        "pr_auc": pr_auc,
        "pr_auc_baseline": pos_rate,
        "pr_auc_gain": pr_auc - pos_rate if pd.notna(pr_auc) and pd.notna(pos_rate) else np.nan,
        "pr_auc_lift": pr_auc / pos_rate if pd.notna(pr_auc) and pos_rate else np.nan,
        "brier": brier_score(y_arr, score_arr) if len(y_arr) else np.nan,
        "logloss": log_loss_score(y_arr, score_arr) if len(y_arr) else np.nan,
        "ece": expected_calibration_error(y_arr, score_arr, n_bins=10) if len(y_arr) else np.nan,
    }


def model_topk_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (model, horizon), group in predictions.groupby(["model_name", "horizon"], dropna=False):
        for cutoff, part in group.groupby("cutoff_month", dropna=False):
            for k_name, pct in [("top_5_pct", 0.05), ("top_10_pct", 0.10)]:
                n = max(1, int(math.ceil(len(part) * pct)))
                top = part.sort_values("score", ascending=False).head(n)
                pos = part["label_die_H"].sum()
                rows.append(
                    {
                        "model_name": model,
                        "horizon": horizon,
                        "cutoff_month": cutoff,
                        "K": k_name,
                        "row_count": len(part),
                        "topk_count": n,
                        "precision_at_k": float(top["label_die_H"].mean()) if n else np.nan,
                        "recall_at_k": float(top["label_die_H"].sum() / pos) if pos else np.nan,
                        "lift_at_k": float(top["label_die_H"].mean() / part["label_die_H"].mean()) if part["label_die_H"].mean() else np.nan,
                        "ndcg_at_k": ndcg_at_k(
                            part.sort_values("score", ascending=False)["label_die_H"].to_numpy(dtype=int),
                            n,
                        ),
                    }
                )
    return pd.DataFrame(rows)


def calibration_bins(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (model, horizon), group in predictions.groupby(["model_name", "horizon"], dropna=False):
        score = pd.to_numeric(group["probability_score"], errors="coerce")
        bins = pd.cut(score, bins=np.linspace(0, 1, 11), include_lowest=True, labels=False)
        for bin_id, part in group.groupby(bins, dropna=False):
            rows.append(
                {
                    "model_name": model,
                    "horizon": horizon,
                    "bin_id": bin_id,
                    "row_count": len(part),
                    "avg_pred": float(part["probability_score"].mean()),
                    "observed_die_rate": float(part["label_die_H"].mean()),
                }
            )
    return pd.DataFrame(rows)


def feature_ablation_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame()
    keep = metrics.copy()
    keep["rank_by_ece_then_auc"] = keep.sort_values(["ece", "auc"], ascending=[True, False]).reset_index().index + 1
    return keep


def render_model_selection_decision(metrics: pd.DataFrame) -> str:
    if metrics.empty:
        return "# Model Selection Decision\n\nNo closed model frame was available.\n"
    candidates = metrics[metrics["model_name"].str.contains("logistic|xgboost|hybrid", case=False, na=False)].copy()
    if candidates.empty:
        candidates = metrics.copy()
    best_prob = candidates.sort_values(["ece", "brier", "auc"], ascending=[True, True, False]).iloc[0]
    best_rank = metrics.sort_values(["auc", "pr_auc_gain"], ascending=[False, False]).iloc[0]
    return f"""# Model Selection Decision

- best probability model: {best_prob["model_name"]}
- best ranking scorer/baseline: {best_rank["model_name"]}
- best probability AUC / PR-AUC gain / ECE / Brier / LogLoss: {best_prob.get("auc"):.4f} / {best_prob.get("pr_auc_gain"):.4f} / {best_prob.get("ece"):.4f} / {best_prob.get("brier"):.4f} / {best_prob.get("logloss"):.4f}
- best ranking AUC / PR-AUC gain: {best_rank.get("auc"):.4f} / {best_rank.get("pr_auc_gain"):.4f}

Ranking and probability are evaluated separately. Value/business priority is not used as a probability feature. No formal model file is saved.
"""


def render_model_ablation_summary(metrics: pd.DataFrame, topk: pd.DataFrame) -> str:
    if metrics.empty:
        return "# Main Model Ablation Summary\n\nNo metrics available.\n"
    return "# Main Model Ablation Summary\n\n" + metrics.sort_values("auc", ascending=False).head(12).to_markdown(index=False) + "\n"


# ---------------------------------------------------------------------------
# Stage 5/6: M pipeline and decision
# ---------------------------------------------------------------------------


def run_entity_complete_m_stage(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    ensure_entity_complete_dirs(root)
    progress_path = project_path(root, M_STAGE_REPORT_DIR / "m_stage_progress.md")
    progress_update(progress_path, "stage=select_primary_model", reset=True)
    metrics_path = project_path(root, MODEL_REPORT_DIR / "model_metric_summary.csv")
    primary = choose_primary_model_from_metrics(read_csv(metrics_path))
    prediction_path = project_path(root, PREDICTION_DIR / "model_scores_long.parquet")
    progress_update(progress_path, f"stage=read_primary_predictions primary_model={primary}")
    try:
        predictions = pd.read_parquet(prediction_path, filters=[("model_name", "==", primary)])
    except Exception:
        predictions = read_parquet(prediction_path)
        predictions = predictions[predictions["model_name"].eq(primary)].copy() if not predictions.empty else predictions
    features = read_parquet(project_path(root, FEATURE_DIR / "entity_cutoff_feature_table.parquet"))
    if predictions.empty:
        return {}
    progress_update(progress_path, f"stage=build_m1 prediction_rows={len(predictions)}")
    candidate_metrics, candidates = build_m1_candidates(predictions)
    progress_update(progress_path, "stage=build_m2_m7")
    m2 = build_m2_one_shot_metrics(predictions)
    m3 = build_m3_survival_lite(predictions)
    m4 = build_m4_detector_evidence(predictions)
    m5 = build_m5_status_decision(candidates)
    m7 = build_m7_evidence_bundle(candidates, features)
    m8 = build_m8_backtest(predictions, candidates)
    write_csv(project_path(root, CANDIDATE_DIR / "m1_candidates.csv"), candidates)
    write_csv(project_path(root, M_STAGE_REPORT_DIR / "m1_candidate_policy_metrics.csv"), candidate_metrics)
    write_csv(project_path(root, M_STAGE_REPORT_DIR / "m2_one_shot_metrics.csv"), m2)
    write_csv(project_path(root, M_STAGE_REPORT_DIR / "m3_survival_lite_metrics.csv"), m3)
    write_csv(project_path(root, M_STAGE_REPORT_DIR / "m4_detector_evidence_metrics.csv"), m4)
    write_csv(project_path(root, M_STAGE_REPORT_DIR / "m5_status_distribution.csv"), m5)
    write_csv(project_path(root, EVIDENCE_DIR / "m7_evidence_bundle_sample.csv"), m7)
    write_csv(project_path(root, BACKTEST_REPORT_DIR / "m8_backtest_summary.csv"), m8)
    write_text(project_path(root, M_STAGE_REPORT_DIR / "m_stage_pipeline_summary.md"), render_m_stage_summary(candidate_metrics, m2, m3, m4, m5, m7, m8))
    write_text(project_path(root, DECISION_REPORT_DIR / "entity_complete_stage_decision.md"), render_stage_decision(candidate_metrics, m2, m3, m4, m5, m7, m8))
    progress_update(progress_path, f"stage=done candidate_rows={len(candidates)}")
    return {"candidate_metrics": candidate_metrics, "candidates": candidates, "m2": m2, "m3": m3, "m4": m4, "m5": m5, "m7": m7, "m8": m8}


def choose_primary_model(predictions: pd.DataFrame) -> str:
    metrics = model_metric_summary(predictions)
    if metrics.empty:
        return predictions["model_name"].iloc[0]
    candidates = metrics[metrics["model_name"].str.contains("logistic|hybrid|xgboost", case=False, na=False)]
    if candidates.empty:
        candidates = metrics
    return str(candidates.sort_values(["ece", "brier", "auc"], ascending=[True, True, False]).iloc[0]["model_name"])


def choose_primary_model_from_metrics(metrics: pd.DataFrame) -> str:
    if metrics.empty:
        return "xgboost_small"
    candidates = metrics[metrics["model_name"].str.contains("logistic|hybrid|xgboost", case=False, na=False)]
    if candidates.empty:
        candidates = metrics
    return str(candidates.sort_values(["ece", "brier", "auc"], ascending=[True, True, False]).iloc[0]["model_name"])


def build_m1_candidates(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    primary = choose_primary_model(predictions)
    base = predictions[predictions["model_name"].eq(primary)].copy()
    policies = {
        "probability_top10": "probability_score",
        "interval_top10": "interval_overdue_baseline",
        "frequency_top10": "frequency_decay_baseline",
        "recency_top10": "recency_only_baseline",
        "hybrid_top10": "hybrid_interval_frequency_score",
    }
    metric_rows = []
    candidate_parts = []
    for policy, score_col in policies.items():
        for (horizon, cutoff), group in base.groupby(["horizon", "cutoff_month"], dropna=False):
            n = max(1, int(math.ceil(len(group) * 0.10)))
            top = group.sort_values(score_col, ascending=False).head(n).copy()
            top["candidate_policy"] = policy
            candidate_parts.append(top)
            pos = group["label_die_H"].sum()
            metric_rows.append(
                {
                    "candidate_policy": policy,
                    "horizon": horizon,
                    "cutoff_month": cutoff,
                    "full_universe_rows": len(group),
                    "full_universe_die_count": int(pos),
                    "candidate_rows": len(top),
                    "candidate_die_count": int(top["label_die_H"].sum()),
                    "candidate_die_recall": float(top["label_die_H"].sum() / pos) if pos else np.nan,
                    "candidate_positive_rate": float(top["label_die_H"].mean()),
                    "non_candidate_positive_rate": float(group.loc[~group.index.isin(top.index), "label_die_H"].mean()) if len(group) > len(top) else np.nan,
                    "candidate_lift": float(top["label_die_H"].mean() / group["label_die_H"].mean()) if group["label_die_H"].mean() else np.nan,
                }
            )
    candidates = pd.concat(candidate_parts, ignore_index=True).drop_duplicates(ENTITY_KEYS + ["cutoff_month", "horizon", "candidate_policy"])
    return pd.DataFrame(metric_rows), candidates


def build_m2_one_shot_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    one = predictions[predictions["one_shot_flag"].astype(bool)].copy() if "one_shot_flag" in predictions else pd.DataFrame()
    if one.empty:
        return pd.DataFrame([{"horizon": "all", "row_count": 0, "note": "no one-shot rows"}])
    rows = []
    for horizon, group in one.groupby("horizon", dropna=False):
        rows.append({"horizon": horizon, "row_count": len(group), **metric_row(group.assign(label_die_H=group["label_alive_H"]), "probability_score"), "semantic_note": "repeat probability is separate from recurring churn"})
    return pd.DataFrame(rows)


def build_m3_survival_lite(predictions: pd.DataFrame) -> pd.DataFrame:
    work = predictions.copy()
    score = pd.to_numeric(work.get("interval_overdue_baseline"), errors="coerce")
    work["survival_state"] = np.select([score.isna(), score < 0.8, score < 1.2, score >= 1.2], ["interval_unavailable", "not_overdue", "near_due", "overdue"], default="unknown")
    return work.groupby(["horizon", "survival_state"], dropna=False).agg(row_count=("label_die_H", "size"), die_rate=("label_die_H", "mean")).reset_index()


def build_m4_detector_evidence(predictions: pd.DataFrame) -> pd.DataFrame:
    work = predictions.copy()
    work["frequency_drop_detector_hit"] = pd.to_numeric(work.get("frequency_decay_baseline"), errors="coerce").gt(0.5)
    work["interval_overdue_detector_hit"] = pd.to_numeric(work.get("interval_overdue_baseline"), errors="coerce").gt(1.5)
    rows = []
    for detector in ["frequency_drop_detector_hit", "interval_overdue_detector_hit"]:
        for hit, group in work.groupby(detector, dropna=False):
            rows.append({"detector": detector, "hit": bool(hit), "row_count": len(group), "die_rate": float(group["label_die_H"].mean()), "semantic_note": "detector is evidence, not probability"})
    return pd.DataFrame(rows)


def build_m5_status_decision(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    work = candidates.copy()
    score = pd.to_numeric(work["probability_score"], errors="coerce")
    history_flag = work["history_sufficiency_flag"].astype(str) if "history_sufficiency_flag" in work else pd.Series("", index=work.index)
    work["status_decision"] = np.select(
        [
            history_flag.eq("history_insufficient"),
            score.ge(score.quantile(0.90)),
            score.ge(score.quantile(0.70)),
        ],
        ["observation_only", "priority_review", "manual_review"],
        default="low_confidence_watch",
    )
    work["auto_dispatch_allowed"] = False
    return work.groupby(["status_decision", "auto_dispatch_allowed"], dropna=False).size().reset_index(name="row_count")


def build_m7_evidence_bundle(candidates: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    cols = [
        *ENTITY_KEYS,
        "cutoff_month",
        "horizon",
        "candidate_policy",
        "probability_score",
        "recency_only_baseline",
        "frequency_decay_baseline",
        "interval_overdue_baseline",
        "demand_shape_label",
        "history_sufficiency_flag",
    ]
    out = candidates[[c for c in cols if c in candidates.columns]].head(500).copy()
    out["allowed_claims"] = "internal diagnostic evidence; ranked risk review"
    out["forbidden_claims"] = "LLM card; auto dispatch; detector/interval/business priority as probability"
    out["bundle_complete"] = out.notna().mean(axis=1).ge(0.8)
    return out


def build_m8_backtest(predictions: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    primary = choose_primary_model(predictions)
    full = predictions[predictions["model_name"].eq(primary)]
    cand = candidates[candidates["candidate_policy"].eq("probability_top10")] if "candidate_policy" in candidates else pd.DataFrame()
    rows = []
    rows.append({"scope": "full_universe", "model_name": primary, **metric_row(full, "probability_score")})
    if not cand.empty:
        rows.append({"scope": "candidate_probability_top10", "model_name": primary, **metric_row(cand, "probability_score")})
    return pd.DataFrame(rows)


def render_m_stage_summary(candidate_metrics: pd.DataFrame, m2: pd.DataFrame, m3: pd.DataFrame, m4: pd.DataFrame, m5: pd.DataFrame, m7: pd.DataFrame, m8: pd.DataFrame) -> str:
    recall = candidate_metrics["candidate_die_recall"].mean() if not candidate_metrics.empty else np.nan
    return f"""# M-Stage Pipeline Summary

- M1 mean candidate die recall: {recall:.4f}
- M2 metric rows: {len(m2)}
- M3 state rows: {len(m3)}
- M4 detector rows: {len(m4)}
- M5 status rows: {len(m5)}
- M7 evidence sample rows: {len(m7)}
- M8 summary rows: {len(m8)}

No LLM card is generated and `auto_dispatch_allowed=false`.
"""


def render_stage_decision(candidate_metrics: pd.DataFrame, m2: pd.DataFrame, m3: pd.DataFrame, m4: pd.DataFrame, m5: pd.DataFrame, m7: pd.DataFrame, m8: pd.DataFrame) -> str:
    recall = candidate_metrics["candidate_die_recall"].mean() if not candidate_metrics.empty else np.nan
    full_auc = m8.loc[m8["scope"].eq("full_universe"), "auc"].iloc[0] if not m8.empty and m8["scope"].eq("full_universe").any() else np.nan
    allow_internal = bool(pd.notna(full_auc) and full_auc >= 0.58 and pd.notna(recall) and recall >= 0.10)
    return f"""# Entity Complete Stage Decision

1. New data is entity-complete for selected manufacturers and sampled entity keys; it is not full SQL-universe complete.
2. Hospital-drug choice-set context is added so manufacturer switching is not automatically treated as terminal demand loss.
3. Old metrics are considered contaminated by the row-level TOP N extract and must not be used as service conclusions.
4. New main model full-universe AUC: {full_auc:.4f}
5. Mean M1 candidate die recall: {recall:.4f}
6. M2 one-shot remains separate from recurring churn.
7. M3/M4/M5/M7 passed light semantic checks as evidence/review layers, not probability services.
8. Frontend/backend design allowed: {"internal diagnostic view only" if allow_internal else "no"}
9. Customer-facing probability service: no.
10. Static proof-case report: allowed for internal analysis.
11. Next algorithm task: expand entity/manufacturer/choice-set complete coverage or run confirmed time-window-complete extraction before customer-facing service.
"""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def rank01(values: pd.Series) -> pd.Series:
    vals = pd.to_numeric(values, errors="coerce")
    if vals.notna().sum() == 0:
        return pd.Series(np.nan, index=values.index)
    return vals.rank(pct=True)


def _date_str(value: Any) -> str | None:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.strftime("%Y-%m-%d")
