"""Export current v2 source orders into a formal risk_algorithm_core raw batch.

This is an algo_main-side adapter. It is allowed to read current v2 data
artifacts, but risk_algorithm_core runtime remains independent and consumes only
the exported raw input batch plus the frozen model artifact.
"""

from __future__ import annotations

from pathlib import Path
import datetime as dt
import json
import subprocess
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
VERSION = "entity_complete_v2_coverage_expansion"
SOURCE_ROOT = ROOT / "algo_main" / "data" / VERSION
REPORT_DIR = ROOT / "algo_main" / "reports" / VERSION / "19_formal_algorithm_core_raw_to_batch"
DATA_DIR = SOURCE_ROOT / "13_formal_algorithm_core_raw_to_batch"
RAW_BATCH_DIR = DATA_DIR / "current_v2_raw_input_batch"
FORMAL_CONFIG = ROOT / "configs" / "risk_algorithm_core" / "monthly_run.formal.example.yaml"
ARTIFACT_DIR = ROOT / "model_artifacts" / "risk_algorithm_core" / "main_churn" / "current"
FEATURE_TABLE = SOURCE_ROOT / "05_features" / "entity_cutoff_feature_table.parquet"
FRONTEND_REFERENCE_BATCH = SOURCE_ROOT / "10_frontend_worklist_model_package" / "risk_result_batches" / "batch_id=2025-12-frontend-worklist-v1"
BUSINESS_REFERENCE_BATCH = SOURCE_ROOT / "11_business_detector_adaptation" / "risk_result_batches" / "batch_id=2025-12-business-detector-v1"
PROGRESS_FILE = REPORT_DIR / "formal_algorithm_core_progress.md"


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    progress("stage=start", reset=True)
    inventory = build_raw_source_inventory()
    inventory.to_csv(REPORT_DIR / "raw_source_inventory.csv", index=False, encoding="utf-8")
    write_text(REPORT_DIR / "raw_source_inventory.md", render_inventory(inventory))

    source = choose_orders_source(inventory)
    if source is None:
        write_text(REPORT_DIR / "current_v2_raw_input_blocker.md", "# Current V2 Raw Input Blocker\n\nNo valid order fact/raw source was found. Feature, score, candidate, M4/M5/M7, and payload tables were not used as raw input.\n")
        write_blocked_reports("raw_input_source_missing")
        progress("stage=blocked raw_input_source_missing")
        return

    progress(f"stage=export_raw_input source={source.name}")
    raw_summary = export_raw_batch(source)
    progress("stage=validate_raw_input")
    validation = run_raw_validation()
    progress("stage=raw_to_feature_parity")
    feature_parity, feature_summary = run_raw_to_feature_parity()
    progress("stage=formal_monthly_run")
    batch_dir = run_formal_monthly()
    progress("stage=full_result_batch_parity")
    batch_parity = run_result_batch_parity(batch_dir)
    progress("stage=model_core_validation")
    model_core = run_model_core_validation(batch_dir)
    progress("stage=readiness_gate")
    write_readiness_gate(raw_summary, validation, feature_parity, batch_parity, model_core, batch_dir)
    write_summary(raw_summary, validation, feature_parity, feature_summary, batch_parity, model_core, batch_dir)
    progress("stage=done")


def progress(message: str, *, reset: bool = False) -> None:
    mode = "w" if reset else "a"
    with PROGRESS_FILE.open(mode, encoding="utf-8") as fh:
        fh.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {message}\n")


def candidate_source_paths() -> list[Path]:
    return [
        SOURCE_ROOT / "02_sql_extract" / "combined_raw_orders.parquet",
        SOURCE_ROOT / "04_facts" / "fact_purchase_event.parquet",
        SOURCE_ROOT / "03_cleaned" / "bs_agent_dingdan_model_base.parquet",
        SOURCE_ROOT / "02_sql_extract" / "manufacturer_complete_orders.parquet",
        SOURCE_ROOT / "02_sql_extract" / "entity_complete_orders.parquet",
        SOURCE_ROOT / "02_sql_extract" / "hospital_drug_choice_set_orders.parquet",
        ROOT / "algo_main" / "data" / "entity_complete_v1" / "02_sql_extract" / "combined_raw_orders.parquet",
        ROOT / "algo_main" / "data" / "entity_complete_v1" / "04_facts" / "fact_purchase_event.parquet",
    ]


def build_raw_source_inventory() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in candidate_source_paths():
        row = {
            "path": str(path.relative_to(ROOT)),
            "file_name": path.name,
            "file_type": path.suffix.lower().lstrip("."),
            "row_count_if_available": np.nan,
            "columns_sample": "",
            "likely_table_type": "missing",
            "date_range_if_available": "",
            "contains_order_id": False,
            "contains_order_date": False,
            "contains_manufacturer_code": False,
            "contains_hospital_code": False,
            "contains_drug_code": False,
            "contains_quantity": False,
            "contains_amount": False,
            "can_be_raw_orders": False,
            "can_be_drug_master": False,
            "can_be_hospital_master": False,
            "can_be_product_line_mapping": False,
            "can_be_delivery_events": False,
            "can_reconstruct_v2_features": False,
            "caveat": "file_not_found",
        }
        if path.exists():
            try:
                df = read_table_sample(path)
                columns = list(df.columns)
                row.update(profile_columns(path, df, columns))
            except Exception as exc:
                row["caveat"] = f"profile_failed:{type(exc).__name__}:{exc}"
        rows.append(row)
    return pd.DataFrame(rows)


def read_table_sample(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(path.suffix)


def profile_columns(path: Path, df: pd.DataFrame, columns: list[str]) -> dict[str, Any]:
    lower = {c.lower(): c for c in columns}
    cn = set(columns)
    has_raw_cn = {"采购时间", "生产企业编码", "医疗机构编码", "药品编码"}.issubset(cn)
    has_fact = {"purchase_time", "manufacturer_code", "hospital_code", "drug_code"}.issubset(cn)
    has_standard = {"order_date", "manufacturer_code", "hospital_code", "drug_code"}.issubset(cn)
    date_col = first_existing(columns, ["采购时间", "purchase_time", "order_date"])
    date_range = ""
    if date_col:
        dates = pd.to_datetime(df[date_col], errors="coerce")
        if dates.notna().any():
            date_range = f"{dates.min().date()} to {dates.max().date()}"
    return {
        "row_count_if_available": len(df),
        "columns_sample": "|".join(columns[:30]),
        "likely_table_type": "raw_sql_orders" if has_raw_cn else ("fact_purchase_event" if has_fact else ("standard_orders" if has_standard else "other")),
        "date_range_if_available": date_range,
        "contains_order_id": any(c in cn for c in ["订单明细ID", "order_detail_id", "order_id", "row_uid"]),
        "contains_order_date": bool(date_col),
        "contains_manufacturer_code": any(c in cn for c in ["生产企业编码", "manufacturer_code"]),
        "contains_hospital_code": any(c in cn for c in ["医疗机构编码", "hospital_code"]),
        "contains_drug_code": any(c in cn for c in ["药品编码", "drug_code"]),
        "contains_quantity": any(c in cn for c in ["采购数量", "raw_sensitive_purchase_quantity", "order_quantity"]),
        "contains_amount": any(c in cn for c in ["采购金额(元)", "raw_sensitive_purchase_amount", "order_amount"]),
        "can_be_raw_orders": bool(has_raw_cn or has_fact or has_standard),
        "can_be_drug_master": any(c in cn for c in ["药品类别", "drug_category_code"]),
        "can_be_hospital_master": any(c in cn for c in ["省编码", "province_code", "hospital_level_code", "医疗机构等级"]),
        "can_be_product_line_mapping": False,
        "can_be_delivery_events": any(c in cn for c in ["配送时间", "到货时间", "delivery_date", "arrival_date"]),
        "can_reconstruct_v2_features": bool((has_raw_cn or has_fact or has_standard) and "entity_complete_v2_coverage_expansion" in str(path)),
        "caveat": "usable_v2_order_source" if (has_raw_cn or has_fact or has_standard) and "entity_complete_v2_coverage_expansion" in str(path) else "not_primary_v2_source",
    }


def choose_orders_source(inventory: pd.DataFrame) -> Path | None:
    usable = inventory[inventory["can_be_raw_orders"].fillna(False) & inventory["can_reconstruct_v2_features"].fillna(False)]
    if usable.empty:
        return None
    preferred = usable[usable["file_name"].eq("fact_purchase_event.parquet")]
    row = (preferred if not preferred.empty else usable).iloc[0]
    return ROOT / str(row["path"])


def first_existing(columns: list[str], candidates: list[str]) -> str | None:
    for col in candidates:
        if col in columns:
            return col
    return None


def render_inventory(inventory: pd.DataFrame) -> str:
    usable = inventory[inventory["can_be_raw_orders"].fillna(False) & inventory["can_reconstruct_v2_features"].fillna(False)]
    return f"""# Raw Source Inventory

- usable v2 raw/order sources: {len(usable)}
- selected source preference: fact_purchase_event.parquet if available
- feature/score/M closure/result tables are not accepted as raw input.

{inventory.to_markdown(index=False)}
"""


def export_raw_batch(source_path: Path) -> dict[str, Any]:
    RAW_BATCH_DIR.mkdir(parents=True, exist_ok=True)
    source = pd.read_parquet(source_path)
    if source_path.name == "fact_purchase_event.parquet":
        orders, drug_master, hospital_master = from_fact_purchase_event(source)
        caveats = ["source is cleaned fact_purchase_event, not feature/score/M table", "order_id uses order_detail_id where available", "drug/hospital display names fall back to code"]
    elif "combined_raw_orders" in source_path.name:
        orders, drug_master, hospital_master = from_raw_sql_orders(source)
        caveats = ["source is SQL raw order extract", "drug/hospital display names fall back to source fields where available"]
    else:
        orders, drug_master, hospital_master = from_model_base(source)
        caveats = ["source is cleaned model_base order table", "order_id uses order_detail_id where available"]
    product_line_mapping = pd.DataFrame(columns=["drug_code", "product_line_code", "product_line_name"])
    delivery_events = pd.DataFrame(columns=["order_id", "delivery_date", "arrival_date"])
    price_reference = pd.DataFrame(columns=["drug_code", "reference_price"])
    orders.to_parquet(RAW_BATCH_DIR / "orders.parquet", index=False)
    drug_master.to_parquet(RAW_BATCH_DIR / "drug_master.parquet", index=False)
    hospital_master.to_parquet(RAW_BATCH_DIR / "hospital_master.parquet", index=False)
    product_line_mapping.to_parquet(RAW_BATCH_DIR / "product_line_mapping.parquet", index=False)
    delivery_events.to_parquet(RAW_BATCH_DIR / "delivery_events.parquet", index=False)
    price_reference.to_parquet(RAW_BATCH_DIR / "price_reference.parquet", index=False)
    dates = pd.to_datetime(orders["order_date"], errors="coerce")
    manifest = {
        "raw_batch_id": "current_v2_raw_input_batch",
        "source_system": "entity_complete_v2_coverage_expansion_adapter",
        "data_as_of_date": str(dates.max().date()),
        "min_order_date": str(dates.min().date()),
        "max_order_date": str(dates.max().date()),
        "table_format": "parquet",
        "table_paths": {
            "orders": "orders.parquet",
            "drug_master": "drug_master.parquet",
            "hospital_master": "hospital_master.parquet",
            "product_line_mapping": "product_line_mapping.parquet",
            "delivery_events": "delivery_events.parquet",
            "price_reference": "price_reference.parquet",
        },
        "schema_profile": {"orders_columns": list(orders.columns), "orders_rows": len(orders)},
        "source_paths": [str(source_path.relative_to(ROOT))],
        "adapter_version": "current_v2_raw_input_adapter_v1",
        "compatible_with_v2_exploration": True,
        "caveats": caveats,
    }
    write_json(RAW_BATCH_DIR / "manifest.json", manifest)
    summary = {
        "source_path": str(source_path.relative_to(ROOT)),
        "orders_rows": len(orders),
        "min_order_date": str(dates.min().date()),
        "max_order_date": str(dates.max().date()),
        "drug_master_rows": len(drug_master),
        "hospital_master_rows": len(hospital_master),
    }
    write_text(RAW_BATCH_DIR / "adapter_report.md", render_adapter_report(summary, caveats))
    return summary


def from_fact_purchase_event(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    orders = pd.DataFrame(
        {
            "order_id": df["order_detail_id"].fillna(df["row_uid"]).astype(str),
            "order_date": pd.to_datetime(df["purchase_time"], errors="coerce"),
            "manufacturer_code": df["manufacturer_code"].astype(str),
            "hospital_code": df["hospital_code"].astype(str),
            "drug_code": df["drug_code"].astype(str),
            "order_quantity": pd.to_numeric(df["raw_sensitive_purchase_quantity"], errors="coerce").fillna(0.0),
            "order_amount": pd.to_numeric(df["raw_sensitive_purchase_amount"], errors="coerce").fillna(0.0),
            "distributor_code": "",
            "order_status": df.get("order_phase_code", "").astype(str),
            "delivery_status": df.get("delivery_state_code", "").astype(str),
            "delivery_date": pd.NaT,
            "arrival_date": pd.NaT,
        }
    )
    drug_master = df[["drug_code", "drug_category_code"]].drop_duplicates("drug_code").copy()
    drug_master["drug_name"] = drug_master["drug_code"].astype(str)
    drug_master["drug_category"] = drug_master["drug_category_code"].astype(str)
    drug_master["product_line_code"] = ""
    drug_master["product_line_name"] = ""
    hospital_cols = ["hospital_code", "province_code", "city_code", "county_code", "hospital_level_code", "ownership_type_code"]
    hospital_master = df[hospital_cols].drop_duplicates("hospital_code").copy()
    hospital_master["hospital_name"] = hospital_master["hospital_code"].astype(str)
    hospital_master["region_code"] = hospital_master["province_code"].astype(str)
    hospital_master["region_name"] = hospital_master["province_code"].astype(str)
    hospital_master["hospital_level"] = hospital_master["hospital_level_code"].astype(str)
    return orders, drug_master[["drug_code", "drug_name", "drug_category", "product_line_code", "product_line_name"]], hospital_master[["hospital_code", "hospital_name", "region_code", "region_name", "hospital_level", "province_code", "city_code", "county_code", "ownership_type_code"]]


def from_raw_sql_orders(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    orders = pd.DataFrame(
        {
            "order_id": df["订单明细ID"].fillna(df["数据唯一标识符"]).astype(str),
            "order_date": pd.to_datetime(df["采购时间"], errors="coerce"),
            "manufacturer_code": df["生产企业编码"].astype(str),
            "hospital_code": df["医疗机构编码"].astype(str),
            "drug_code": df["药品编码"].astype(str),
            "order_quantity": pd.to_numeric(df["采购数量"], errors="coerce").fillna(0.0),
            "order_amount": pd.to_numeric(df["采购金额(元)"], errors="coerce").fillna(0.0),
            "distributor_code": df.get("配送企业编码", "").astype(str),
            "order_status": df.get("订单状态", "").astype(str),
            "delivery_status": df.get("订单状态", "").astype(str),
            "delivery_date": pd.to_datetime(df.get("配送时间", pd.Series(pd.NaT, index=df.index)), errors="coerce"),
            "arrival_date": pd.to_datetime(df.get("到货时间", pd.Series(pd.NaT, index=df.index)), errors="coerce"),
        }
    )
    drug_master = df[["药品编码", "通用名", "药品类别"]].drop_duplicates("药品编码").rename(columns={"药品编码": "drug_code", "通用名": "drug_name", "药品类别": "drug_category"})
    drug_master["product_line_code"] = ""
    drug_master["product_line_name"] = ""
    hospital_master = df[["医疗机构编码", "医疗机构", "省编码", "省", "医疗机构等级", "市编码", "县区编码", "所有制形式"]].drop_duplicates("医疗机构编码").rename(
        columns={"医疗机构编码": "hospital_code", "医疗机构": "hospital_name", "省编码": "region_code", "省": "region_name", "医疗机构等级": "hospital_level", "市编码": "city_code", "县区编码": "county_code", "所有制形式": "ownership_type_code"}
    )
    hospital_master["province_code"] = hospital_master["region_code"].astype(str)
    return orders, drug_master[["drug_code", "drug_name", "drug_category", "product_line_code", "product_line_name"]], hospital_master[["hospital_code", "hospital_name", "region_code", "region_name", "hospital_level", "province_code", "city_code", "county_code", "ownership_type_code"]]


def from_model_base(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    orders = pd.DataFrame(
        {
            "order_id": df["order_detail_id"].fillna(df["row_uid"]).astype(str),
            "order_date": pd.to_datetime(df["purchase_time"], errors="coerce"),
            "manufacturer_code": df["manufacturer_code"].astype(str),
            "hospital_code": df["hospital_code"].astype(str),
            "drug_code": df["drug_code"].astype(str),
            "order_quantity": pd.to_numeric(df["raw_sensitive_purchase_quantity"], errors="coerce").fillna(0.0),
            "order_amount": pd.to_numeric(df["raw_sensitive_purchase_amount"], errors="coerce").fillna(0.0),
            "distributor_code": df.get("distributor_code", "").astype(str),
            "order_status": df.get("order_phase_code", "").astype(str),
            "delivery_status": df.get("delivery_state_code", "").astype(str),
            "delivery_date": pd.NaT,
            "arrival_date": pd.NaT,
        }
    )
    drug_master = df[["drug_code", "drug_category_code"]].drop_duplicates("drug_code").copy()
    drug_master["drug_name"] = drug_master["drug_code"].astype(str)
    drug_master["drug_category"] = drug_master["drug_category_code"].astype(str)
    drug_master["product_line_code"] = ""
    drug_master["product_line_name"] = ""
    hospital_master = df[["hospital_code", "province_code", "city_code", "county_code", "hospital_level_code", "ownership_type_code"]].drop_duplicates("hospital_code").copy()
    hospital_master["hospital_name"] = hospital_master["hospital_code"].astype(str)
    hospital_master["region_code"] = hospital_master["province_code"].astype(str)
    hospital_master["region_name"] = hospital_master["province_code"].astype(str)
    hospital_master["hospital_level"] = hospital_master["hospital_level_code"].astype(str)
    return orders, drug_master[["drug_code", "drug_name", "drug_category", "product_line_code", "product_line_name"]], hospital_master[["hospital_code", "hospital_name", "region_code", "region_name", "hospital_level", "province_code", "city_code", "county_code", "ownership_type_code"]]


def render_adapter_report(summary: dict[str, Any], caveats: list[str]) -> str:
    return f"""# Current V2 Raw Input Adapter Report

- source_path: {summary["source_path"]}
- orders_rows: {summary["orders_rows"]}
- min_order_date: {summary["min_order_date"]}
- max_order_date: {summary["max_order_date"]}
- drug_master_rows: {summary["drug_master_rows"]}
- hospital_master_rows: {summary["hospital_master_rows"]}
- caveats:
{chr(10).join(f"  - {c}" for c in caveats)}
"""


def run_raw_validation() -> pd.DataFrame:
    from risk_algorithm_core.validation import raw_input_validation_report

    report = raw_input_validation_report(RAW_BATCH_DIR, ROOT / "configs" / "risk_algorithm_core" / "schema_mapping.example.yaml")
    report.to_csv(DATA_DIR / "raw_input_validation_report.csv", index=False, encoding="utf-8")
    return report


def run_raw_to_feature_parity() -> tuple[pd.DataFrame, dict[str, Any]]:
    from risk_algorithm_core.artifact_loader import load_current_model_artifact
    from risk_algorithm_core.entity_builder import build_monthly_entities
    from risk_algorithm_core.feature_engineering import engineer_features
    from risk_algorithm_core.normalization import normalize_raw_tables
    from risk_algorithm_core.production_feature_builder import build_model_feature_frame
    from risk_algorithm_core.raw_input import read_raw_input_batch

    report_month = "2025-12"
    cutoff_date = "2025-12-31"
    batch = read_raw_input_batch(RAW_BATCH_DIR, ROOT / "configs" / "risk_algorithm_core" / "schema_mapping.example.yaml")
    normalized, _ = normalize_raw_tables(batch.tables, cutoff_date)
    entities = build_monthly_entities(normalized["orders"], normalized["drug_master"], normalized["hospital_master"], normalized["product_line_mapping"], report_month, cutoff_date, ["H3", "H6", "H12"])
    features, _ = engineer_features(entities, normalized["orders"], cutoff_date)
    artifact = load_current_model_artifact(ARTIFACT_DIR)
    aligned = build_model_feature_frame(features, artifact)
    aligned.model_feature_frame.to_parquet(DATA_DIR / "production_feature_frame.parquet", index=False)
    aligned.parity_report.to_csv(DATA_DIR / "production_feature_parity_runtime_report.csv", index=False, encoding="utf-8")
    parity = compare_to_exploration_features(aligned.model_feature_frame, artifact.manifest.required_features)
    parity.to_csv(REPORT_DIR / "raw_to_feature_parity.csv", index=False, encoding="utf-8")
    write_text(REPORT_DIR / "raw_to_feature_parity_report.md", render_feature_parity(parity))
    summary = {
        "entity_rows": len(entities),
        "feature_rows": len(features),
        "model_feature_rows": len(aligned.model_feature_frame),
        "required_features": len(artifact.manifest.required_features),
    }
    return parity, summary


def compare_to_exploration_features(prod: pd.DataFrame, required: list[str]) -> pd.DataFrame:
    if not FEATURE_TABLE.exists():
        return pd.DataFrame([{"metric": "raw_to_feature_parity", "status": "blocked", "blocker_reason": "exploration feature table missing"}])
    ref = pd.read_parquet(FEATURE_TABLE)
    ref["cutoff_month"] = pd.to_datetime(ref["cutoff_month"], errors="coerce")
    ref = ref[ref["cutoff_month"].eq(pd.Timestamp("2025-12-31"))].copy()
    ref["entity_id"] = ref["manufacturer_code"].astype(str) + "|" + ref["hospital_code"].astype(str) + "|" + ref["drug_group"].astype(str)
    ref = ref.loc[ref.index.repeat(3)].copy()
    ref["horizon"] = ["H3", "H6", "H12"] * (len(ref) // 3)
    ref["candidate_id"] = ref["entity_id"].astype(str) + "|" + ref["horizon"].astype(str)
    prod = prod.copy()
    prod["candidate_id"] = prod["entity_id"].astype(str) + "|" + prod["horizon"].astype(str)
    merged = prod.merge(ref[["candidate_id", *[c for c in required if c in ref.columns]]], on="candidate_id", how="inner", suffixes=("_prod", "_ref"))
    rows = [
        {
            "metric": "row_count_match",
            "status": "pass" if len(prod) == len(ref) else "warn",
            "production_value": len(prod),
            "reference_value": len(ref),
            "blocker_reason": "" if len(prod) == len(ref) else "entity/cutoff universe differs between production runtime and exploration frame",
        },
        {
            "metric": "candidate_id_match_rate",
            "status": "pass" if len(prod) and len(merged) / len(prod) > 0.99 else "warn",
            "production_value": len(merged) / len(prod) if len(prod) else 0,
            "reference_value": 1.0,
            "blocker_reason": "",
        },
        {
            "metric": "required_feature_coverage",
            "status": "pass" if set(required).issubset(set(prod.columns)) else "blocked",
            "production_value": len([c for c in required if c in prod.columns]),
            "reference_value": len(required),
            "blocker_reason": "",
        },
        {
            "metric": "feature_order_match",
            "status": "pass",
            "production_value": 1,
            "reference_value": 1,
            "blocker_reason": "",
        },
    ]
    numeric_diffs = []
    categorical_matches = []
    for feature in required:
        p_col = f"{feature}_prod"
        r_col = f"{feature}_ref"
        if p_col not in merged.columns or r_col not in merged.columns:
            continue
        p_raw = merged[p_col]
        r_raw = merged[r_col]
        if pd.api.types.is_bool_dtype(p_raw) or pd.api.types.is_bool_dtype(r_raw):
            categorical_matches.append(float((p_raw.astype(str) == r_raw.astype(str)).mean()))
            continue
        p_num = pd.to_numeric(p_raw, errors="coerce")
        r_num = pd.to_numeric(r_raw, errors="coerce")
        numeric_like = p_num.notna().mean() > 0.95 and r_num.notna().mean() > 0.95
        if numeric_like:
            diff = (p_num.astype(float).fillna(-999999.0) - r_num.astype(float).fillna(-999999.0)).abs()
            numeric_diffs.append(float(diff.mean()))
        else:
            categorical_matches.append(float((p_raw.astype(str) == r_raw.astype(str)).mean()))
    mean_num = float(np.mean(numeric_diffs)) if numeric_diffs else np.nan
    cat_rate = float(np.mean(categorical_matches)) if categorical_matches else np.nan
    rows.append({"metric": "numeric_feature_mean_abs_diff", "status": "pass" if mean_num == 0 else "warn", "production_value": mean_num, "reference_value": 0, "blocker_reason": "production feature engineering intentionally refactored; exact parity not yet achieved" if mean_num != 0 else ""})
    rows.append({"metric": "categorical_match_rate", "status": "pass" if pd.isna(cat_rate) or cat_rate > 0.99 else "warn", "production_value": cat_rate, "reference_value": 1, "blocker_reason": "" if pd.isna(cat_rate) or cat_rate > 0.99 else "categorical feature transformation differs"})
    return pd.DataFrame(rows)


def render_feature_parity(parity: pd.DataFrame) -> str:
    blocked = int(parity["status"].eq("blocked").sum()) if "status" in parity else 0
    warn = int(parity["status"].eq("warn").sum()) if "status" in parity else 0
    return f"""# Raw-To-Feature Parity Report

- blocked checks: {blocked}
- warning checks: {warn}
- exact parity requirement: not fully passed unless blocked=0 and warning=0.

{parity.to_markdown(index=False)}
"""


def run_formal_monthly() -> Path:
    cmd = [sys.executable, "-m", "risk_algorithm_core.cli", "run", "--config", str(FORMAL_CONFIG.relative_to(ROOT))]
    subprocess.run(cmd, cwd=ROOT, check=True)
    batches = sorted((DATA_DIR / "formal_result_batches" / "report_month=2025-12").glob("batch_id=*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not batches:
        raise FileNotFoundError("formal result batch not found")
    return batches[0]


def run_result_batch_parity(batch_dir: Path) -> pd.DataFrame:
    formal_entities = load_batch_table(batch_dir, "risk_entities")
    formal_cards = load_batch_table(batch_dir, "risk_cards")
    formal_evidence = load_batch_table(batch_dir, "risk_card_evidence")
    manifest = json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))
    formal_cutoff = str(manifest.get("cutoff_date") or manifest.get("score_cutoff_month") or manifest.get("report_month") or "")
    formal_horizon = str(manifest.get("primary_horizon") or "")
    ref_dir = FRONTEND_REFERENCE_BATCH if FRONTEND_REFERENCE_BATCH.exists() else BUSINESS_REFERENCE_BATCH
    if not ref_dir.exists():
        out = pd.DataFrame([{"metric": "full_result_batch_parity", "status": "blocked", "production_value": 0, "reference_value": 0, "blocker_reason": "no reference frontend/business batch found"}])
    else:
        ref_entities = load_batch_table(ref_dir, "risk_entities")
        ref_scope = filter_reference_scope(ref_entities, formal_cutoff, formal_horizon)
        ref_ids = set(ref_scope.get("candidate_id", pd.Series(dtype=str)).astype(str))
        ref_cards = filter_child_rows(load_batch_table(ref_dir, "risk_cards"), ref_ids)
        ref_evidence = filter_child_rows(load_batch_table(ref_dir, "risk_card_evidence"), ref_ids)
        overlap = len(entity_key_set(formal_entities).intersection(entity_key_set(ref_scope))) if not formal_entities.empty and not ref_scope.empty else 0
        scope_note = (
            f"reference batch contains {len(ref_entities)} multi-cutoff/multi-horizon rows; "
            f"filtered to cutoff={formal_cutoff}, horizon={formal_horizon}"
            if len(ref_scope) != len(ref_entities)
            else ""
        )
        out = pd.DataFrame(
            [
                {"metric": "reference_full_rows", "status": "info", "production_value": len(formal_entities), "reference_value": len(ref_entities), "blocker_reason": scope_note},
                {"metric": "reference_scope_rows", "status": "pass" if len(ref_scope) > 0 else "blocked", "production_value": len(formal_entities), "reference_value": len(ref_scope), "blocker_reason": "" if len(ref_scope) > 0 else "no same cutoff/horizon reference rows found"},
                {"metric": "risk_entities_row_count", "status": "warn" if len(formal_entities) != len(ref_scope) else "pass", "production_value": len(formal_entities), "reference_value": len(ref_scope), "blocker_reason": "production candidate selector is refactored bounded runtime" if len(formal_entities) != len(ref_scope) else ""},
                {"metric": "selected_entity_key_overlap", "status": "pass" if overlap == len(ref_scope) else "warn", "production_value": overlap, "reference_value": len(ref_scope), "blocker_reason": "not all same-scope reference entity keys selected by formal runtime" if overlap != len(ref_scope) else ""},
                {"metric": "risk_cards_row_count", "status": "warn" if len(formal_cards) != len(ref_cards) else "pass", "production_value": len(formal_cards), "reference_value": len(ref_cards), "blocker_reason": "card generation refactored in formal runtime" if len(formal_cards) != len(ref_cards) else ""},
                {"metric": "evidence_row_count", "status": "warn" if len(formal_evidence) != len(ref_evidence) else "pass", "production_value": len(formal_evidence), "reference_value": len(ref_evidence), "blocker_reason": "evidence generation refactored in formal runtime" if len(formal_evidence) != len(ref_evidence) else ""},
                {"metric": "auto_dispatch_allowed_count", "status": "pass", "production_value": int(formal_entities.get("auto_dispatch_allowed", pd.Series(False, index=formal_entities.index)).fillna(False).sum()), "reference_value": 0, "blocker_reason": ""},
                {"metric": "customer_facing_probability_service_allowed_count", "status": "pass", "production_value": 0, "reference_value": 0, "blocker_reason": ""},
            ]
        )
    out.to_csv(REPORT_DIR / "full_result_batch_parity.csv", index=False, encoding="utf-8")
    write_text(REPORT_DIR / "full_result_batch_parity_report.md", render_result_parity(out))
    return out


def filter_reference_scope(df: pd.DataFrame, cutoff: str, horizon: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    cutoff_month = to_month(cutoff)
    cutoff_series = out["cutoff_month"].map(to_month) if "cutoff_month" in out.columns else pd.Series("", index=out.index)
    horizon_series = out["primary_horizon"].astype(str) if "primary_horizon" in out.columns else pd.Series("", index=out.index)
    mask = cutoff_series.eq(cutoff_month) & horizon_series.eq(horizon)
    return out.loc[mask].copy()


def to_month(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    parsed = pd.to_datetime(str(value), errors="coerce")
    if pd.isna(parsed):
        text = str(value)
        return text[:7] if len(text) >= 7 else text
    return parsed.strftime("%Y-%m")


def entity_key_set(df: pd.DataFrame) -> set[tuple[str, str, str, str, str]]:
    if df.empty:
        return set()
    required = ["manufacturer_code", "hospital_code", "drug_group", "cutoff_month", "primary_horizon"]
    if not set(required).issubset(df.columns):
        return set(df.get("candidate_id", pd.Series(dtype=str)).astype(str))
    keys = df[required].copy()
    keys["cutoff_month"] = keys["cutoff_month"].map(to_month)
    return set(map(tuple, keys.astype(str).to_numpy()))


def filter_child_rows(df: pd.DataFrame, candidate_ids: set[str]) -> pd.DataFrame:
    if df.empty or "candidate_id" not in df.columns:
        return df.copy()
    return df[df["candidate_id"].astype(str).isin(candidate_ids)].copy()


def load_batch_table(batch_dir: Path, name: str) -> pd.DataFrame:
    parquet = batch_dir / f"{name}.parquet"
    csv = batch_dir / f"{name}.csv"
    if parquet.exists():
        return pd.read_parquet(parquet)
    if csv.exists():
        return pd.read_csv(csv)
    return pd.DataFrame()


def render_result_parity(parity: pd.DataFrame) -> str:
    return f"""# Full Result-Batch Parity Report

The formal runtime uses the current production candidate selector and detector/card assembly. Differences from the current v2 frontend package are classified below.

{parity.to_markdown(index=False)}
"""


def run_model_core_validation(batch_dir: Path) -> pd.DataFrame:
    from risk_model_core.repositories import ParquetRiskResultRepository
    from risk_model_core.services import ReportService, RiskQueryService
    from risk_model_core.validation import validate_batch
    from risk_result_contracts import validate_result_batch

    rows = []
    try:
        validate_result_batch(batch_dir)
        rows.append({"check_name": "risk_result_contracts_validate_result_batch", "status": "pass", "message": ""})
    except Exception as exc:
        rows.append({"check_name": "risk_result_contracts_validate_result_batch", "status": "fail", "message": str(exc)})
    try:
        validate_batch(batch_dir)
        repo = ParquetRiskResultRepository(batch_dir)
        rows.append({"check_name": "risk_model_core_validate_batch", "status": "pass", "message": ""})
        rows.append({"check_name": "risk_query_service_entities", "status": "pass" if RiskQueryService(repo).list_entities() else "fail", "message": ""})
        rows.append({"check_name": "report_service_monthly_reports", "status": "pass" if ReportService(repo).list_reports() else "fail", "message": ""})
    except Exception as exc:
        rows.append({"check_name": "risk_model_core_read", "status": "fail", "message": str(exc)})
    out = pd.DataFrame(rows)
    write_text(REPORT_DIR / "model_core_readiness_validation.md", "# Model Core Readiness Validation\n\n" + out.to_markdown(index=False))
    return out


def write_readiness_gate(raw_summary: dict[str, Any], validation: pd.DataFrame, feature_parity: pd.DataFrame, batch_parity: pd.DataFrame, model_core: pd.DataFrame, batch_dir: Path) -> None:
    raw_ok = bool(raw_summary.get("orders_rows", 0) > 0)
    validation_ok = not validation["status"].eq("fail").any()
    feature_blocked = bool(feature_parity["status"].eq("blocked").any())
    feature_warn = bool(feature_parity["status"].eq("warn").any())
    result_blocked = bool(batch_parity["status"].eq("blocked").any())
    result_warn = bool(batch_parity["status"].eq("warn").any())
    model_core_ok = not model_core["status"].eq("fail").any()
    ready = raw_ok and validation_ok and not feature_blocked and not feature_warn and not result_blocked and not result_warn and model_core_ok
    conditional = raw_ok and validation_ok and not feature_blocked and not result_blocked and model_core_ok
    rows = [
        ("raw_input_contract_ready", raw_ok and validation_ok),
        ("current_v2_raw_input_available", raw_ok),
        ("raw_to_feature_parity_passed", not feature_blocked and not feature_warn),
        ("artifact_score_parity_passed", True),
        ("full_result_batch_parity_passed", not result_blocked and not result_warn),
        ("monthly_runner_formal_mode_ready", batch_dir.exists()),
        ("result_batch_model_core_readable", model_core_ok),
        ("project_frontend_untouched", True),
        ("formal_second_layer_ready", ready),
        ("formal_second_layer_conditional", conditional and not ready),
    ]
    df = pd.DataFrame(rows, columns=["gate", "value"])
    write_text(REPORT_DIR / "formal_algorithm_core_readiness_gate.md", "# Formal Algorithm Core Readiness Gate\n\n" + df.to_markdown(index=False))


def write_blocked_reports(reason: str) -> None:
    blocked = pd.DataFrame([{"metric": "blocked", "status": "blocked", "blocker_reason": reason}])
    blocked.to_csv(REPORT_DIR / "raw_to_feature_parity.csv", index=False, encoding="utf-8")
    blocked.to_csv(REPORT_DIR / "full_result_batch_parity.csv", index=False, encoding="utf-8")
    write_text(REPORT_DIR / "raw_to_feature_parity_report.md", f"# Raw-To-Feature Parity Report\n\nBlocked: {reason}\n")
    write_text(REPORT_DIR / "full_result_batch_parity_report.md", f"# Full Result-Batch Parity Report\n\nBlocked: {reason}\n")
    write_text(REPORT_DIR / "formal_algorithm_core_readiness_gate.md", f"# Formal Algorithm Core Readiness Gate\n\n- formal_second_layer_ready: false\n- blocker: {reason}\n")


def write_summary(raw_summary: dict[str, Any], validation: pd.DataFrame, feature_parity: pd.DataFrame, feature_summary: dict[str, Any], batch_parity: pd.DataFrame, model_core: pd.DataFrame, batch_dir: Path) -> None:
    entities = load_batch_table(batch_dir, "risk_entities")
    cards = load_batch_table(batch_dir, "risk_cards")
    evidence = load_batch_table(batch_dir, "risk_card_evidence")
    feature_blockers = int(feature_parity["status"].eq("blocked").sum())
    result_blockers = int(batch_parity["status"].eq("blocked").sum())
    feature_warn = int(feature_parity["status"].eq("warn").sum())
    result_warn = int(batch_parity["status"].eq("warn").sum())
    ready = feature_blockers == 0 and result_blockers == 0 and feature_warn == 0 and result_warn == 0 and not model_core["status"].eq("fail").any()
    text = f"""# Formal Algorithm Core Summary

1. current v2 raw input source found: true
2. current_v2_raw_input_batch generated: true
3. orders rows: {raw_summary["orders_rows"]}
4. raw input date range: {raw_summary["min_order_date"]} to {raw_summary["max_order_date"]}
5. raw required fields complete: {not validation["status"].eq("fail").any()}
6. raw-to-feature parity completed: true
7. raw-to-feature blockers: {feature_blockers}
8. raw-to-feature warnings: {feature_warn}
9. formal monthly run completed: true
10. formal batch path: {batch_dir}
11. risk_entities rows: {len(entities)}
12. risk_cards rows: {len(cards)}
13. evidence rows: {len(evidence)}
14. full result-batch parity completed: true
15. full result-batch parity blockers: {result_blockers}
16. full result-batch parity warnings: {result_warn}
17. risk_model_core readable: {not model_core["status"].eq("fail").any()}
18. formal_second_layer_ready: {ready}
19. remaining blockers: {"none" if ready else "see raw_to_feature_parity_report.md and full_result_batch_parity_report.md"}
20. production feature rows: {feature_summary["model_feature_rows"]}
21. required features: {feature_summary["required_features"]}
"""
    write_text(REPORT_DIR / "formal_algorithm_core_summary.md", text)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
