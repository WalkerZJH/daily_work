"""Reusable BS_Agent_DingDan v2 cleaning pipeline.

This module is the production-oriented entry point for freezing the stable v2
cleaning logic. It does not build models or detector features; it only produces
a model-ready base table plus optional clean/audit samples and quality reports.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text

from alg.cleaning.bs_agent_dingdan import (
    CleaningPaths,
    build_clean_model_audit_v2,
    build_column_maps,
    build_numeric_desensitization_report_v2,
    build_order_status_mapping_coverage,
    build_order_status_suspicious_mapping,
    build_order_status_lifecycle_map,
    field_profile,
    load_env,
    load_yaml,
    projected_columns_sql,
    quote_sqlserver_identifier,
)


MODEL_FORBIDDEN_TEXT_COLUMNS = {
    "hospital_name",
    "distributor_name",
    "manufacturer_name",
    "product_name",
    "order_status_raw",
    "hospital_level_raw",
    "hospital_level_label",
    "ownership_type_raw",
    "drug_category_raw",
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _pipeline_paths(project_root: Path, output_dir: str | Path, raw_cache_path: str | Path | None) -> CleaningPaths:
    output_root = Path(output_dir)
    if not output_root.is_absolute():
        output_root = project_root / output_root
    raw_path = Path(raw_cache_path) if raw_cache_path is not None else project_root / "data/01_raw/BS_Agent_DingDan.parquet"
    if not raw_path.is_absolute():
        raw_path = project_root / raw_path
    return CleaningPaths(
        project_root=project_root,
        config_path=project_root / "configs/data_schema/bs_agent_dingdan_schema.yaml",
        status_map_path=project_root / "configs/mappings/order_status_map.yaml",
        hospital_level_map_path=project_root / "configs/mappings/hospital_grade_map.yaml",
        export_eda=output_root / "eda",
        export_clean=output_root / "clean",
        export_mappings=output_root / "mappings",
        raw_parquet_path=raw_path,
        clean_parquet_path=project_root / "data/03_cleaned/bs_agent_dingdan_clean.parquet",
        sample_csv_path=output_root / "raw/BS_Agent_DingDan_sample.csv",
    )


def _ensure_pipeline_dirs(paths: CleaningPaths) -> None:
    for path in [paths.export_eda, paths.export_clean, paths.export_mappings, paths.raw_parquet_path.parent]:
        path.mkdir(parents=True, exist_ok=True)


def _read_raw_cache(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported raw cache format: {path.suffix}")


def _write_raw_cache(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".parquet":
        df.to_parquet(path, index=False)
        return
    if path.suffix.lower() == ".csv":
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return
    raise ValueError(f"Unsupported raw cache format: {path.suffix}")


def _read_sql_projected(
    sql_database_url: str | None,
    engine: Any | None,
    table_name: str,
    raw_columns: list[str],
    max_rows: int | None,
    sample_mode: bool,
    chunksize: int,
) -> pd.DataFrame:
    if engine is None:
        if not sql_database_url:
            raise RuntimeError("A SQLAlchemy engine, sql_database_url, or existing raw_cache_path is required.")
        engine = create_engine(sql_database_url)
    effective_max_rows = max_rows
    if sample_mode and effective_max_rows is None:
        effective_max_rows = 5000
    projection = projected_columns_sql(raw_columns)
    top_clause = f"TOP ({int(effective_max_rows)}) " if effective_max_rows is not None else ""
    sql = f"SELECT {top_clause}{projection} FROM {quote_sqlserver_identifier(table_name)}"
    if effective_max_rows is not None:
        return pd.read_sql(text(sql), engine)
    chunks = pd.read_sql(text(sql), engine, chunksize=chunksize)
    return pd.concat(chunks, ignore_index=True)


def _load_raw_dataframe(
    sql_database_url: str | None,
    engine: Any | None,
    table_name: str,
    raw_columns: list[str],
    raw_cache_path: Path,
    max_rows: int | None,
    sample_mode: bool,
    chunksize: int,
    write_outputs: bool,
) -> pd.DataFrame:
    if raw_cache_path.exists():
        return _read_raw_cache(raw_cache_path)
    df = _read_sql_projected(
        sql_database_url=sql_database_url,
        engine=engine,
        table_name=table_name,
        raw_columns=raw_columns,
        max_rows=max_rows,
        sample_mode=sample_mode,
        chunksize=chunksize,
    )
    if write_outputs and raw_cache_path.suffix.lower() == ".parquet":
        _write_raw_cache(df, raw_cache_path)
    return df


def _write_dataframe_outputs(
    df: pd.DataFrame,
    parquet_path: Path,
    csv_path: Path,
    output_format: str,
    sample_mode: bool,
) -> dict[str, str]:
    written: dict[str, str] = {}
    if output_format in {"parquet", "both"}:
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(parquet_path, index=False)
        written["parquet"] = str(parquet_path)
    if output_format in {"csv", "both"}:
        if not sample_mode:
            raise ValueError("CSV output is only allowed in sample/debug mode.")
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        written["csv"] = str(csv_path)
    return written


def _write_field_quality_gate(clean_v2: pd.DataFrame, model_base: pd.DataFrame, audit: pd.DataFrame, export_eda: Path) -> Path:
    profile = field_profile(clean_v2)
    model_columns = set(model_base.columns)
    audit_columns = set(audit.columns)
    profile["in_model_base"] = profile["column"].isin(model_columns)
    profile["in_audit"] = profile["column"].isin(audit_columns)
    profile["recommended_default_x_role"] = profile["column"].map(
        lambda c: "trace_key" if c in {"row_uid", "order_detail_id"} else "time_index" if c == "purchase_time" else "quality_flag" if c == "region_dirty_flag" else "candidate_base"
    )
    path = export_eda / "field_quality_gate_v2.csv"
    profile.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _status_distribution(df: pd.DataFrame, column: str) -> list[str]:
    if column not in df:
        return []
    counts = df[column].value_counts(dropna=False).sort_index()
    return [f"- {column}={value}: {int(count)}" for value, count in counts.items()]


def _build_quality_report(
    clean_v2: pd.DataFrame,
    model_base: pd.DataFrame,
    audit: pd.DataFrame,
    numeric_report: pd.DataFrame,
    output_paths: dict[str, Any],
) -> str:
    row_count = len(clean_v2)
    field_count = clean_v2.shape[1]
    duplicate_groups = int(clean_v2["order_detail_id"].duplicated(keep=False).sum()) if "order_detail_id" in clean_v2 else 0
    coverage = build_order_status_mapping_coverage(clean_v2)
    summary = dict(zip(coverage["metric"], coverage["value"]))
    contradictions = numeric_report[numeric_report["metric_group"] == "status_quantity_contradiction"]
    contradiction_lines = "\n".join(f"- {r.metric}: {r.value}" for r in contradictions.itertuples(index=False))
    output_lines = "\n".join(f"- {key}: {value}" for key, value in output_paths.items())
    return f"""# BS_Agent_DingDan v2 Pipeline Quality Report

## Scope

- Rows: {row_count}
- Columns in clean_v2: {field_count}
- model_base rows/columns: {model_base.shape[0]} / {model_base.shape[1]}
- audit rows/columns: {audit.shape[0]} / {audit.shape[1]}

## Identifier Checks

- row_uid unique: {bool(clean_v2['row_uid'].is_unique) if 'row_uid' in clean_v2 else None}
- order_detail_id unique: {bool(clean_v2['order_detail_id'].is_unique) if 'order_detail_id' in clean_v2 else None}
- order_detail_id duplicated-row count: {duplicate_groups}

## Field Quality

See `field_quality_gate_v2.csv` for null count, null rate, and distinct count.

## Region Checks

{chr(10).join(_status_distribution(clean_v2, 'region_dirty_flag'))}

## Drug Code Checks

{chr(10).join(_status_distribution(audit, 'drug_code_match_flag'))}
{chr(10).join(_status_distribution(audit, 'drug_code_conflict_flag'))}

## Status Mapping

- total_rows: {summary.get('total_rows')}
- mapped_rows: {summary.get('mapped_rows')}
- unmapped_rows: {summary.get('unmapped_rows')}
- mapping_coverage: {summary.get('mapping_coverage')}

Needs manual review:
{chr(10).join(_status_distribution(clean_v2, 'needs_manual_review'))}

Order phase:
{chr(10).join(_status_distribution(clean_v2, 'order_phase_code'))}

Delivery state:
{chr(10).join(_status_distribution(clean_v2, 'delivery_state_code'))}

## Numeric Checks

See `numeric_desensitization_report_v2.csv` for zero rate, negative rate, ratio distribution, and gt_1_rate. `gt_1_rate` uses non-null ratio rows as denominator.

## Status / Quantity Contradictions

{contradiction_lines}

## model_base Usage Notes

- `model_base` is a stable base table, not final `X_train`.
- `row_uid` and `order_detail_id` are trace keys and must not directly enter X.
- `purchase_time` is a time index for sorting, splitting, and aggregation; do not use it as a plain continuous feature.
- `region_dirty_flag` is a quality-control flag and should not enter X by default.
- Status semantic fields may leak labels for completion, failure, terminal, arrival, or delivery-quality tasks.
- Ratio fields such as `delivery_rate` and `arrival_rate` come from quantities; they are not delivery-duration features.
- Do not infer unit price from amount / quantity, and do not validate purchase price against amount / quantity.

## Output Paths

{output_lines}
"""


def run_bs_agent_dingdan_cleaning_pipeline(
    sql_database_url: str | None = None,
    engine: Any | None = None,
    table_name: str = "BS_Agent_DingDan",
    output_dir: str | Path = "exports",
    raw_cache_path: str | Path | None = None,
    output_format: str = "parquet",
    max_rows: int | None = None,
    sample_mode: bool = True,
    chunksize: int = 100_000,
    generate_model: bool = True,
    generate_clean: bool = False,
    generate_audit: bool = False,
    generate_quality_report: bool = True,
    write_outputs: bool = True,
    return_dataframes: bool = False,
    use_polars: bool = True,
) -> dict:
    """Run the frozen BS_Agent_DingDan v2 cleaning pipeline.

    `use_polars` is reserved for a future backend. The current implementation
    uses projected SQL reads plus pandas cleaning to preserve the verified v2
    semantics.
    """

    if output_format not in {"parquet", "csv", "both"}:
        raise ValueError("output_format must be one of: parquet, csv, both")
    if output_format in {"csv", "both"} and not sample_mode:
        raise ValueError("CSV output is only allowed in sample/debug mode.")
    project_root = _project_root()
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if not write_outputs:
        temp_dir = tempfile.TemporaryDirectory()
        output_dir = Path(temp_dir.name) / "exports"
        if raw_cache_path is None:
            raw_cache_path = Path(temp_dir.name) / "raw.parquet"
    paths = _pipeline_paths(project_root, output_dir, raw_cache_path)
    _ensure_pipeline_dirs(paths)
    schema = load_yaml(paths.config_path)
    hospital_level_map = load_yaml(paths.hospital_level_map_path)
    raw_to_alias, _, raw_columns = build_column_maps(schema)
    df_raw = _load_raw_dataframe(
        sql_database_url=sql_database_url,
        engine=engine,
        table_name=table_name,
        raw_columns=raw_columns,
        raw_cache_path=paths.raw_parquet_path,
        max_rows=max_rows,
        sample_mode=sample_mode,
        chunksize=chunksize,
        write_outputs=write_outputs,
    )
    clean_v2, model_base, audit = build_clean_model_audit_v2(
        df_raw,
        paths=paths,
        schema=schema,
        raw_to_alias=raw_to_alias,
        hospital_level_map=hospital_level_map,
    )
    if MODEL_FORBIDDEN_TEXT_COLUMNS.intersection(model_base.columns):
        bad_columns = sorted(MODEL_FORBIDDEN_TEXT_COLUMNS.intersection(model_base.columns))
        raise RuntimeError(f"model_base contains forbidden text columns: {bad_columns}")
    numeric_report = build_numeric_desensitization_report_v2(clean_v2, paths.export_eda)
    suspicious = build_order_status_suspicious_mapping(clean_v2)
    suspicious.to_csv(paths.export_eda / "order_status_suspicious_mapping.csv", index=False, encoding="utf-8-sig")
    coverage = build_order_status_mapping_coverage(clean_v2)
    coverage.to_csv(paths.export_eda / "order_status_mapping_coverage.csv", index=False, encoding="utf-8-sig")
    build_order_status_lifecycle_map(paths.export_mappings)
    output_paths: dict[str, Any] = {}
    if write_outputs and generate_model:
        output_paths["model_base"] = _write_dataframe_outputs(
            model_base,
            paths.export_clean / "bs_agent_dingdan_model_base.parquet",
            paths.export_clean / "bs_agent_dingdan_model_base.csv",
            output_format=output_format,
            sample_mode=sample_mode,
        )
    if write_outputs and generate_clean:
        if not sample_mode:
            raise ValueError("clean sample output is only allowed in sample/debug mode.")
        clean_path = paths.export_clean / "bs_agent_dingdan_clean_sample_v2.csv"
        clean_v2.to_csv(clean_path, index=False, encoding="utf-8-sig")
        output_paths["clean_sample_v2"] = str(clean_path)
    if write_outputs and generate_audit:
        if not sample_mode:
            raise ValueError("audit sample output is only allowed in sample/debug mode.")
        audit_path = paths.export_clean / "bs_agent_dingdan_audit_sample.csv"
        audit.to_csv(audit_path, index=False, encoding="utf-8-sig")
        output_paths["audit_sample"] = str(audit_path)
    field_gate_path = _write_field_quality_gate(clean_v2, model_base, audit, paths.export_eda)
    output_paths["field_quality_gate_v2"] = str(field_gate_path)
    output_paths["numeric_desensitization_report_v2"] = str(paths.export_eda / "numeric_desensitization_report_v2.csv")
    output_paths["order_status_mapping_coverage"] = str(paths.export_eda / "order_status_mapping_coverage.csv")
    output_paths["order_status_suspicious_mapping"] = str(paths.export_eda / "order_status_suspicious_mapping.csv")
    output_paths["order_status_lifecycle_map"] = str(paths.export_mappings / "order_status_lifecycle_map.csv")
    if generate_quality_report:
        report = _build_quality_report(clean_v2, model_base, audit, numeric_report, output_paths)
        if write_outputs:
            report_path = paths.export_eda / "bs_agent_dingdan_quality_report_v2.md"
            report_path.write_text(report, encoding="utf-8")
            output_paths["quality_report"] = str(report_path)
    result: dict[str, Any] = {
        "row_count": len(clean_v2),
        "model_columns": list(model_base.columns),
        "output_paths": output_paths,
        "sample_mode": sample_mode,
        "output_format": output_format,
        "used_polars": False,
    }
    if return_dataframes:
        result["dataframes"] = {"clean": clean_v2, "model_base": model_base, "audit": audit}
    if temp_dir is not None:
        temp_dir.cleanup()
    return result


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run BS_Agent_DingDan v2 cleaning pipeline.")
    parser.add_argument("--table", default="BS_Agent_DingDan")
    parser.add_argument("--output-dir", default="exports")
    parser.add_argument("--raw-cache-path", default=None)
    parser.add_argument("--output-format", choices=["parquet", "csv", "both"], default="parquet")
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--chunksize", type=int, default=100_000)
    parser.add_argument("--full", action="store_true", help="Disable sample mode. CSV outputs are blocked.")
    parser.add_argument("--generate-model", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--generate-clean", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--generate-audit", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--generate-quality-report", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    project_root = _project_root()
    sql_database_url, env_table = load_env(project_root)
    result = run_bs_agent_dingdan_cleaning_pipeline(
        sql_database_url=sql_database_url,
        table_name=args.table or env_table,
        output_dir=args.output_dir,
        raw_cache_path=args.raw_cache_path,
        output_format=args.output_format,
        max_rows=args.max_rows,
        sample_mode=not args.full,
        chunksize=args.chunksize,
        generate_model=args.generate_model,
        generate_clean=args.generate_clean,
        generate_audit=args.generate_audit,
        generate_quality_report=args.generate_quality_report,
    )
    for key, value in result["output_paths"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
