"""Coverage expansion pipeline for entity-complete alive prediction v2.

The pipeline expands manufacturer/entity/choice-set coverage without
overwriting ``entity_complete_v1``. It reuses the proven v1 cleaning and feature
builders by redirecting their artifact paths inside this module, then performs a
focused stability validation instead of blind tuning.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import importlib.util
import os
import re
import time
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from alg.tasks.die_prediction import entity_complete_rebuild as rebuild
from alg.tasks.die_prediction import entity_complete_algorithm_consolidation as consolidation
from alg.tasks.die_prediction.entity_complete_probability_availability_gate import (
    build_probability_availability_gate,
    render_gate_summary,
    render_service_gate_decision,
)
from alg.tasks.die_prediction.sql_sampling_integrity_audit import (
    load_sql_context,
    mask_database_url,
    query_sql_dataframe,
)


VERSION = "entity_complete_v2_coverage_expansion"
DATA_ROOT = Path(f"data/{VERSION}")
REPORT_ROOT = Path(f"reports/{VERSION}")
PROGRESS_PATH = REPORT_ROOT / "coverage_expansion_progress.md"

TIER_CONFIGS = {
    "tier_small": {"manufacturers": 6, "entities": 3000, "choice_set_pairs": 6000},
    "tier_medium": {"manufacturers": 8, "entities": 5000, "choice_set_pairs": 10000},
    "tier_large": {"manufacturers": 12, "entities": 10000, "choice_set_pairs": 20000},
}

V1_SELECTED_MANUFACTURER_PATH = Path("data/entity_complete_v1/02_sql_extract/extract_manufacturer_keys.csv")
MAX_EXTRACTED_DETAIL_ROWS_FOR_AUTO_CONTINUE = 1_500_000


def run_entity_complete_v2_coverage_expansion(
    project_root: str | Path,
    *,
    tier: str = "tier_medium",
    dry_run: bool = False,
    estimate_only: bool = False,
    query_timeout: int = 240,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    config = TIER_CONFIGS.get(tier, TIER_CONFIGS["tier_medium"])
    ensure_dirs(root)
    progress(root, f"stage=start tier={tier} dry_run={dry_run} estimate_only={estimate_only}", reset=True)

    sql_available = check_sql_available(root)
    if not sql_available and not dry_run:
        write_sql_unavailable_plan(root)
        progress(root, "stage=sql_unavailable_stop")
        return {"status": "sql_unavailable"}

    if sql_available and not dry_run and not estimate_only:
        tier, config = maybe_downgrade_tier_by_estimate(root, tier, config, query_timeout=query_timeout)

    with redirected_rebuild_paths():
        progress(root, "stage=extraction_design")
        patch_manufacturer_selector(root)
        try:
            extract = rebuild.run_entity_complete_sql_extract(
                root,
                max_manufacturers=config["manufacturers"],
                max_entities=config["entities"],
                max_hospital_drug_pairs=config["choice_set_pairs"],
                dry_run=dry_run,
                estimate_only=estimate_only,
                refresh=False,
                query_timeout=query_timeout,
            )
        finally:
            restore_manufacturer_selector()
        write_extraction_design_reports(root, extract, tier, sql_available)
        if estimate_only:
            progress(root, "stage=estimate_only_stop")
            return {"status": "estimate_only", "extract": extract}
        detail_rows = int(extract.get("manufacturer_rows", 0)) + int(extract.get("entity_rows", 0)) + int(extract.get("hospital_drug_rows", 0))
        if detail_rows > MAX_EXTRACTED_DETAIL_ROWS_FOR_AUTO_CONTINUE and not dry_run:
            write_too_large_stop_report(root, detail_rows)
            progress(root, f"stage=detail_rows_too_large_stop rows={detail_rows}")
            return {"status": "detail_rows_too_large", "extract": extract}

        progress(root, "stage=cleaning")
        cleaning = rebuild.run_entity_complete_cleaning(root)
        write_v2_extraction_reports(root, extract, cleaning)

        progress(root, "stage=feature_build")
        features = rebuild.run_entity_complete_feature_build(root)

    progress(root, "stage=leakage_audit")
    frame = load_v2_feature_label_frame(root)
    closed = frame[frame["label_window_closed"].astype(bool)].copy()
    closed["split"] = consolidation.assign_strict_split(closed)
    leakage = consolidation.audit_feature_leakage(frame)
    write_leakage_reports(root, leakage)
    if bool(leakage["possible_future_leakage"].fillna(False).any()):
        write_blocking_leakage_report(root, leakage)
        progress(root, "stage=blocking_leakage_stop")
        return {"status": "blocking_leakage", "leakage": leakage}

    progress(root, "stage=model_validation")
    model_outputs = run_v2_model_validation(root, closed)

    progress(root, "stage=candidate_policy_v2")
    candidate_outputs = run_v2_candidate_policy(root, model_outputs["selected_predictions"])

    progress(root, "stage=probability_gate")
    gate = run_v2_probability_gate(root, candidate_outputs["candidate_rows"], leakage_clean=True)

    progress(root, "stage=interface_readiness")
    interface = run_interface_readiness_audit(root, gate)

    progress(root, "stage=stage_decision")
    write_final_stage_decision(root, model_outputs, candidate_outputs, gate, interface)
    progress(root, "stage=done")
    return {
        "status": "done",
        "extract": extract,
        "cleaning": cleaning,
        "features": features,
        "model_outputs": model_outputs,
        "candidate_outputs": candidate_outputs,
        "gate": gate,
    }


def maybe_downgrade_tier_by_estimate(root: Path, tier: str, config: dict[str, int], *, query_timeout: int) -> tuple[str, dict[str, int]]:
    if tier == "tier_small":
        return tier, config
    with redirected_rebuild_paths():
        progress(root, f"stage=pre_extract_estimate tier={tier}")
        patch_manufacturer_selector(root)
        try:
            estimate = rebuild.run_entity_complete_sql_extract(
                root,
                max_manufacturers=config["manufacturers"],
                max_entities=config["entities"],
                max_hospital_drug_pairs=config["choice_set_pairs"],
                dry_run=False,
                estimate_only=True,
                refresh=False,
                query_timeout=query_timeout,
            )
        finally:
            restore_manufacturer_selector()
    estimated_rows = estimated_detail_rows(estimate)
    write_pre_extract_estimate_report(root, tier, estimate, estimated_rows)
    if estimated_rows > MAX_EXTRACTED_DETAIL_ROWS_FOR_AUTO_CONTINUE:
        downgraded = "tier_small"
        progress(root, f"stage=auto_downgrade from={tier} to={downgraded} estimated_rows={estimated_rows}")
        return downgraded, TIER_CONFIGS[downgraded]
    return tier, config


def estimated_detail_rows(extract: dict[str, Any]) -> int:
    selected_mfg = extract.get("selected_manufacturers", pd.DataFrame())
    selected_entities = extract.get("selected_entities", pd.DataFrame())
    selected_pairs = extract.get("selected_hospital_drug_pairs", pd.DataFrame())
    manufacturer_rows = pd.to_numeric(selected_mfg.get("sql_row_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    entity_rows = pd.to_numeric(selected_entities.get("sql_order_count_total", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    pair_rows = pd.to_numeric(selected_pairs.get("all_pair_order_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    return int(manufacturer_rows + entity_rows + pair_rows)


def write_pre_extract_estimate_report(root: Path, tier: str, extract: dict[str, Any], estimated_rows: int) -> None:
    out = root / REPORT_ROOT / "01_extraction_design"
    out.mkdir(parents=True, exist_ok=True)
    text = f"""# Pre-Extract Row Estimate

- requested tier: {tier}
- estimated detail rows: {estimated_rows}
- auto-continue threshold: {MAX_EXTRACTED_DETAIL_ROWS_FOR_AUTO_CONTINUE}
- selected manufacturers: {len(extract.get("selected_manufacturers", []))}
- selected entities: {len(extract.get("selected_entities", []))}
- selected hospital-drug choice-set pairs: {len(extract.get("selected_hospital_drug_pairs", []))}

If the estimate exceeds the threshold, the run automatically downgrades to tier_small instead of pulling an oversized extract.
"""
    (out / "pre_extract_row_estimate.md").write_text(text, encoding="utf-8")


@contextmanager
def redirected_rebuild_paths():
    keys = [
        "VERSION",
        "DATA_ROOT",
        "REPORT_ROOT",
        "RAW_EXTRACT_DIR",
        "CLEAN_DIR",
        "FACT_DIR",
        "FEATURE_DIR",
        "PREDICTION_DIR",
        "CANDIDATE_DIR",
        "EVIDENCE_DIR",
        "EXTRACT_REPORT_DIR",
        "CLEAN_REPORT_DIR",
        "FEATURE_REPORT_DIR",
        "MODEL_REPORT_DIR",
        "M_STAGE_REPORT_DIR",
        "BACKTEST_REPORT_DIR",
        "DECISION_REPORT_DIR",
        "RAW_OUTPUT_FILES",
    ]
    old = {key: getattr(rebuild, key) for key in keys}
    try:
        rebuild.VERSION = VERSION
        rebuild.DATA_ROOT = DATA_ROOT
        rebuild.REPORT_ROOT = REPORT_ROOT
        rebuild.RAW_EXTRACT_DIR = DATA_ROOT / "02_sql_extract"
        rebuild.CLEAN_DIR = DATA_ROOT / "03_cleaned"
        rebuild.FACT_DIR = DATA_ROOT / "04_facts"
        rebuild.FEATURE_DIR = DATA_ROOT / "05_features"
        rebuild.PREDICTION_DIR = DATA_ROOT / "06_predictions"
        rebuild.CANDIDATE_DIR = DATA_ROOT / "07_candidates"
        rebuild.EVIDENCE_DIR = DATA_ROOT / "08_evidence"
        rebuild.EXTRACT_REPORT_DIR = REPORT_ROOT / "02_extraction"
        rebuild.CLEAN_REPORT_DIR = REPORT_ROOT / "02_extraction" / "cleaning_audit"
        rebuild.FEATURE_REPORT_DIR = REPORT_ROOT / "03_feature_build"
        rebuild.MODEL_REPORT_DIR = REPORT_ROOT / "04_model_validation"
        rebuild.M_STAGE_REPORT_DIR = REPORT_ROOT / "07_candidate_policy_v2"
        rebuild.BACKTEST_REPORT_DIR = REPORT_ROOT / "07_candidate_policy_v2"
        rebuild.DECISION_REPORT_DIR = REPORT_ROOT / "09_stage_decision"
        rebuild.RAW_OUTPUT_FILES = {
            "manufacturer_orders": DATA_ROOT / "02_sql_extract" / "manufacturer_complete_orders.parquet",
            "entity_orders": DATA_ROOT / "02_sql_extract" / "entity_complete_orders.parquet",
            "hospital_drug_choice_set_orders": DATA_ROOT / "02_sql_extract" / "hospital_drug_choice_set_orders.parquet",
            "entity_keys": DATA_ROOT / "02_sql_extract" / "extract_entity_keys.csv",
            "manufacturer_keys": DATA_ROOT / "02_sql_extract" / "extract_manufacturer_keys.csv",
            "hospital_drug_pairs": DATA_ROOT / "02_sql_extract" / "extract_hospital_drug_pairs.csv",
        }
        yield
    finally:
        for key, value in old.items():
            setattr(rebuild, key, value)


_ORIG_SELECT_MANUFACTURERS = None


def patch_manufacturer_selector(root: Path) -> None:
    global _ORIG_SELECT_MANUFACTURERS
    if _ORIG_SELECT_MANUFACTURERS is not None:
        return
    _ORIG_SELECT_MANUFACTURERS = rebuild.select_manufacturers

    def select_v2(profile: pd.DataFrame, *, max_manufacturers: int = 8, min_rows: int = 200_000, target_rows: int = 900_000) -> pd.DataFrame:
        if profile.empty:
            return _ORIG_SELECT_MANUFACTURERS(profile, max_manufacturers=max_manufacturers, min_rows=min_rows, target_rows=target_rows)
        df = profile.copy()
        df["manufacturer_code"] = df["manufacturer_code"].astype(str)
        df["sql_row_count"] = pd.to_numeric(df["sql_row_count"], errors="coerce").fillna(0)
        df["active_months_2020_2026"] = pd.to_numeric(df.get("active_months_2020_2026"), errors="coerce").fillna(0)
        v1_codes: list[str] = []
        v1_path = root / V1_SELECTED_MANUFACTURER_PATH
        if v1_path.exists():
            v1_codes = pd.read_csv(v1_path)["manufacturer_code"].astype(str).tolist()
        selected_parts = []
        if v1_codes:
            selected_parts.append(df[df["manufacturer_code"].isin(v1_codes)].copy())
        remaining = df[~df["manufacturer_code"].isin(v1_codes)].copy()
        stable = remaining[(remaining["active_months_2020_2026"] >= 36) & (remaining["sql_row_count"] >= 5_000)].copy()
        if stable.empty:
            stable = remaining
        selected = pd.concat(selected_parts, ignore_index=True).drop_duplicates("manufacturer_code") if selected_parts else pd.DataFrame(columns=df.columns)
        selected["selection_reason"] = "v1_selected_manufacturer_retained"
        row_budget = {6: 900_000, 8: 1_200_000, 12: 1_500_000}.get(max_manufacturers, 1_200_000)
        current_rows = float(selected["sql_row_count"].sum()) if "sql_row_count" in selected else 0.0
        high = stable.sort_values("sql_row_count", ascending=False).assign(selection_reason="v2_high_volume_stable")
        mid = stable[(stable["sql_row_count"] < stable["sql_row_count"].quantile(0.85)) & (stable["sql_row_count"] > stable["sql_row_count"].quantile(0.25))].sort_values("sql_row_count", ascending=False).assign(selection_reason="v2_mid_volume_stable")
        low = stable[stable["sql_row_count"] <= stable["sql_row_count"].quantile(0.35)].sort_values(["active_months_2020_2026", "sql_row_count"], ascending=[False, False]).assign(selection_reason="v2_lower_volume_stable")
        fallback = stable.sort_values(["active_months_2020_2026", "sql_row_count"], ascending=[False, False]).assign(selection_reason="v2_stability_fallback")
        candidate_order = pd.concat([low, mid, high, fallback], ignore_index=True).drop_duplicates("manufacturer_code")
        candidate_order = candidate_order[~candidate_order["manufacturer_code"].isin(selected["manufacturer_code"].astype(str))]
        additions = []
        for _, row in candidate_order.iterrows():
            row_count = float(row.get("sql_row_count", 0) or 0)
            if len(selected) + len(additions) >= max_manufacturers:
                break
            if current_rows + row_count <= row_budget:
                additions.append(row)
                current_rows += row_count
        if additions:
            selected = pd.concat([selected, pd.DataFrame(additions)], ignore_index=True)
        selected["selection_row_budget"] = row_budget
        selected["selection_estimated_rows_total"] = current_rows
        return selected.reset_index(drop=True)

    rebuild.select_manufacturers = select_v2


def restore_manufacturer_selector() -> None:
    global _ORIG_SELECT_MANUFACTURERS
    if _ORIG_SELECT_MANUFACTURERS is not None:
        rebuild.select_manufacturers = _ORIG_SELECT_MANUFACTURERS
        _ORIG_SELECT_MANUFACTURERS = None


def ensure_dirs(root: Path) -> None:
    dirs = [
        DATA_ROOT / "01_raw_reference",
        DATA_ROOT / "02_sql_extract",
        DATA_ROOT / "03_cleaned",
        DATA_ROOT / "04_facts",
        DATA_ROOT / "05_features",
        DATA_ROOT / "06_predictions",
        DATA_ROOT / "07_candidates",
        DATA_ROOT / "08_service_gate",
        REPORT_ROOT / "01_extraction_design",
        REPORT_ROOT / "02_extraction",
        REPORT_ROOT / "03_leakage_audit",
        REPORT_ROOT / "04_model_validation",
        REPORT_ROOT / "05_calibration",
        REPORT_ROOT / "06_generalization",
        REPORT_ROOT / "07_candidate_policy_v2",
        REPORT_ROOT / "08_service_gate",
        REPORT_ROOT / "09_stage_decision",
        REPORT_ROOT / "10_frontend_backend_interface_readiness",
    ]
    for d in dirs:
        (root / d).mkdir(parents=True, exist_ok=True)


def check_sql_available(root: Path) -> bool:
    try:
        context = load_sql_context(root)
        if not context.sql_database_url:
            return False
        engine = create_engine(context.sql_database_url)
        query_sql_dataframe(engine, "SELECT 1 AS ok", query_timeout=30)
        return True
    except Exception as exc:
        write_sql_unavailable_plan(root, str(exc))
        return False


def write_sql_unavailable_plan(root: Path, reason: str = "") -> None:
    path = root / REPORT_ROOT / "01_extraction_design" / "sql_unavailable_coverage_expansion_plan.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_reason = sanitize_secret_text(reason)
    path.write_text(
        f"""# SQL Unavailable Coverage Expansion Plan

- SQL available: false
- reason: {safe_reason}
- action: do not run real coverage expansion training.
- fallback: use existing entity_complete_v1 only for dry-run interface checks.
""",
        encoding="utf-8",
    )


def sanitize_secret_text(text: str) -> str:
    safe = str(text or "")
    env_url = os.environ.get("SQL_DATABASE_URL")
    if env_url:
        safe = safe.replace(env_url, mask_database_url(env_url))
    safe = re.sub(r"([A-Za-z][A-Za-z0-9+.-]*://)([^@\s]+)@", r"\1***:***@", safe)
    safe = re.sub(r"(?i)(password|pwd)=([^;,\s]+)", r"\1=***", safe)
    return safe


def write_extraction_design_reports(root: Path, extract: dict[str, Any], tier: str, sql_available: bool) -> None:
    out = root / REPORT_ROOT / "01_extraction_design"
    out.mkdir(parents=True, exist_ok=True)
    selected = extract.get("selected_manufacturers", pd.DataFrame()).copy()
    if not selected.empty:
        selected.to_csv(out / "manufacturer_selection_audit.csv", index=False, encoding="utf-8")
    config = TIER_CONFIGS.get(tier, TIER_CONFIGS["tier_medium"])
    decision = f"""# Extraction Scope Decision

- version: {VERSION}
- tier: {tier}
- SQL available: {sql_available}
- target manufacturers/entities/choice pairs: {config}
- selected manufacturer count: {len(selected)}
- selected entity count: {len(extract.get("selected_entities", []))}
- selected hospital-drug pair count: {len(extract.get("selected_hospital_drug_pairs", []))}
- rule: retain v1 manufacturers and add size/stability strata.
- no full SQL universe export is performed.
"""
    (out / "extraction_scope_decision.md").write_text(decision, encoding="utf-8")


def write_v2_extraction_reports(root: Path, extract: dict[str, Any], cleaning: dict[str, Any]) -> None:
    out = root / REPORT_ROOT / "02_extraction"
    out.mkdir(parents=True, exist_ok=True)
    counts = pd.DataFrame(
        [
            {"source": "manufacturer_complete", "row_count": int(extract.get("manufacturer_rows", 0))},
            {"source": "entity_complete", "row_count": int(extract.get("entity_rows", 0))},
            {"source": "hospital_drug_choice_set", "row_count": int(extract.get("hospital_drug_rows", 0))},
            {"source": "clean_model_base", "row_count": len(cleaning.get("model_base", []))},
        ]
    )
    counts.to_csv(out / "extraction_counts_by_source.csv", index=False, encoding="utf-8")
    completeness = root / REPORT_ROOT / "02_extraction" / "entity_history_completeness_after_extract.csv"
    if completeness.exists():
        pd.read_csv(completeness).to_csv(out / "entity_history_completeness_audit.csv", index=False, encoding="utf-8")
    summary = f"""# Extraction Summary

- manufacturer rows: {extract.get("manufacturer_rows", 0)}
- entity rows: {extract.get("entity_rows", 0)}
- choice-set rows: {extract.get("hospital_drug_rows", 0)}
- clean model_base rows: {len(cleaning.get("model_base", []))}
- row-level TOP N sampling: false
- entity-complete selected keys: true
- manufacturer-complete selected manufacturers: true
- choice-set scope: partial platform context only
"""
    (out / "extraction_summary.md").write_text(summary, encoding="utf-8")
    (out / "choice_set_scope_audit.md").write_text(
        "# Choice-Set Scope Audit\n\nChoice-set rows are extracted for selected hospital-drug pairs only. They are partial platform context and must not be described as full market share or confirmed competitor substitution.\n",
        encoding="utf-8",
    )


def write_too_large_stop_report(root: Path, detail_rows: int) -> None:
    path = root / REPORT_ROOT / "02_extraction" / "coverage_expansion_too_large_stop.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Coverage Expansion Stopped\n\nExtracted detail rows `{detail_rows}` exceeded automatic continuation threshold `{MAX_EXTRACTED_DETAIL_ROWS_FOR_AUTO_CONTINUE}`. Rerun with a smaller tier or confirm continuation explicitly.\n",
        encoding="utf-8",
    )


def load_v2_feature_label_frame(root: Path) -> pd.DataFrame:
    features = pd.read_parquet(root / DATA_ROOT / "05_features" / "entity_cutoff_feature_table.parquet")
    labels = pd.read_parquet(root / DATA_ROOT / "05_features" / "alive_labels_H3_H6_H12.parquet")
    features["cutoff_month"] = pd.to_datetime(features["cutoff_month"], errors="coerce")
    labels["cutoff_month"] = pd.to_datetime(labels["cutoff_month"], errors="coerce")
    merged = features.merge(labels, on=["manufacturer_code", "hospital_code", "drug_group", "cutoff_month"], how="left", suffixes=("", "_label"))
    rows = []
    for h in rebuild.HORIZONS:
        part = merged.copy()
        part["horizon"] = f"H{h}"
        part["label_die_H"] = part[f"label_die_H{h}"]
        part["label_alive_H"] = part[f"label_alive_H{h}"]
        part["label_window_closed"] = part[f"label_window_closed_H{h}"].astype(bool)
        rows.append(part)
    return rebuild.add_baseline_scores(pd.concat(rows, ignore_index=True))


def write_leakage_reports(root: Path, leakage: pd.DataFrame) -> None:
    out = root / REPORT_ROOT / "03_leakage_audit"
    out.mkdir(parents=True, exist_ok=True)
    leakage.to_csv(out / "leakage_feature_audit.csv", index=False, encoding="utf-8")
    leakage.to_csv(out / "label_feature_boundary_audit.csv", index=False, encoding="utf-8")
    blocking = int(leakage["possible_future_leakage"].fillna(False).sum())
    (out / "leakage_audit_summary.md").write_text(
        f"# Leakage Audit Summary\n\n- blocking leakage feature count: {blocking}\n- cutoff/as-of feature naming audit completed.\n- choice-set features remain partial-platform context only.\n",
        encoding="utf-8",
    )


def write_blocking_leakage_report(root: Path, leakage: pd.DataFrame) -> None:
    out = root / REPORT_ROOT / "03_leakage_audit"
    bad = leakage[leakage["possible_future_leakage"].fillna(False)]
    (out / "blocking_leakage_report.md").write_text("# Blocking Leakage Report\n\n" + bad.to_markdown(index=False), encoding="utf-8")


def run_v2_model_validation(root: Path, closed: pd.DataFrame) -> dict[str, Any]:
    report = root / REPORT_ROOT
    feature_sets_all = consolidation.build_feature_sets(closed)
    selected_sets = {
        key: feature_sets_all[key]
        for key in [
            "base_recency_frequency",
            "base_plus_interval",
            "base_plus_demand_shape",
            "all_safe_features_without_choice_set",
            "all_safe_features_with_choice_set",
            "all_features",
        ]
        if key in feature_sets_all
    }
    model_dir = report / "04_model_validation"
    model_dir.mkdir(parents=True, exist_ok=True)
    summary, by_horizon, _ = consolidation.run_feature_group_ablation(closed, selected_sets, model_dir)
    summary.to_csv(model_dir / "feature_group_ablation_summary.csv", index=False, encoding="utf-8")
    by_horizon.to_csv(model_dir / "feature_group_ablation_by_horizon.csv", index=False, encoding="utf-8")
    model_family = run_limited_model_family(closed, selected_sets, model_dir)
    model_family.to_csv(model_dir / "model_family_comparison.csv", index=False, encoding="utf-8")
    tuning, selected_predictions, selected_config = run_v2_xgb_tuning(closed, selected_sets, model_dir)
    tuning.to_csv(model_dir / "xgboost_sanity_grid.csv", index=False, encoding="utf-8")
    cal, bins, calibrated, decision = consolidation.run_calibration_comparison(selected_predictions)
    cal_dir = report / "05_calibration"
    cal_dir.mkdir(parents=True, exist_ok=True)
    cal.to_csv(cal_dir / "calibration_comparison.csv", index=False, encoding="utf-8")
    bins.to_csv(cal_dir / "calibration_bins_by_horizon.csv", index=False, encoding="utf-8")
    (cal_dir / "calibration_decision.md").write_text(decision, encoding="utf-8")
    calibrated = calibrated.reset_index(drop=True)
    gen_dir = report / "06_generalization"
    gen_dir.mkdir(parents=True, exist_ok=True)
    learning = consolidation.run_learning_curve(closed, selected_sets, selected_config, gen_dir)
    holdout = consolidation.run_manufacturer_holdout(closed, selected_sets, selected_config, gen_dir)
    period = consolidation.cutoff_period_generalization(calibrated)
    learning.to_csv(gen_dir / "training_window_learning_curve.csv", index=False, encoding="utf-8")
    holdout.to_csv(gen_dir / "manufacturer_holdout_generalization.csv", index=False, encoding="utf-8")
    period.to_csv(gen_dir / "cutoff_period_generalization.csv", index=False, encoding="utf-8")
    write_coverage_vs_metric_summary(gen_dir, summary, holdout)
    pred_path = root / DATA_ROOT / "06_predictions" / "selected_model_predictions.parquet"
    pred_path.parent.mkdir(parents=True, exist_ok=True)
    calibrated.to_parquet(pred_path, index=False)
    return {
        "ablation": summary,
        "model_family": model_family,
        "tuning": tuning,
        "selected_predictions": calibrated,
        "selected_config": selected_config,
        "calibration": cal,
        "learning": learning,
        "holdout": holdout,
        "period": period,
    }


def run_limited_model_family(closed: pd.DataFrame, feature_sets: dict[str, list[str]], report_dir: Path) -> pd.DataFrame:
    rows = []
    model_names = ["logistic_regression", "xgboost_small", "lightgbm_small", "catboost_small"]
    set_names = ["base_recency_frequency", "base_plus_interval", "all_safe_features_without_choice_set", "all_safe_features_with_choice_set"]
    for fs in set_names:
        cols = feature_sets.get(fs, [])
        for model in model_names:
            if model == "lightgbm_small" and importlib.util.find_spec("lightgbm") is None:
                rows.append(consolidation.skipped_model_row(fs, model, "dependency_not_installed"))
                continue
            if model == "catboost_small" and importlib.util.find_spec("catboost") is None:
                rows.append(consolidation.skipped_model_row(fs, model, "dependency_not_installed"))
                continue
            progress_path = report_dir
            consolidation.progress(progress_path, f"stage=v2_model_family feature_set={fs} model={model}")
            start = time.time()
            preds = consolidation.train_model_by_horizon(closed, cols, model, params=consolidation.default_model_params(model), eval_split="test", feature_set=fs)
            row = {"feature_set": fs, "model_name": model, "status": "ok", "runtime_seconds": time.time() - start, "feature_count": len(cols), "feature_dependency_complexity": consolidation.feature_dependency_complexity(fs)}
            row.update(consolidation.metric_row_with_topk(preds, "probability_score") if not preds.empty else {"row_count": 0})
            rows.append(row)
        for baseline in ["recency_only_baseline", "interval_overdue_baseline"]:
            preds = consolidation.baseline_predictions(closed[closed["split"].eq("test")].copy(), baseline, fs)
            row = {"feature_set": fs, "model_name": baseline, "status": "ok", "runtime_seconds": 0.0, "feature_count": 1, "feature_dependency_complexity": "rule_baseline"}
            row.update(consolidation.metric_row_with_topk(preds, "probability_score") if not preds.empty else {"row_count": 0})
            rows.append(row)
    return pd.DataFrame(rows)


def run_v2_xgb_tuning(closed: pd.DataFrame, feature_sets: dict[str, list[str]], report_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    fs = "all_safe_features_without_choice_set"
    cols = feature_sets[fs]
    grid = []
    for n in [80, 120]:
        for depth in [3, 4]:
            for lr in [0.05, 0.1]:
                for subsample in [0.8, 1.0]:
                    grid.append({"n_estimators": n, "max_depth": depth, "learning_rate": lr, "subsample": subsample, "colsample_bytree": 0.9, "min_child_weight": 1, "reg_lambda": 1, "reg_alpha": 0})
    grid = grid[:8]
    rows = []
    best = None
    best_key = (float("inf"), float("inf"), -float("inf"))
    for i, params in enumerate(grid, 1):
        consolidation.progress(report_dir, f"stage=v2_xgb_sanity_grid config={i}/{len(grid)}")
        valid = consolidation.train_model_by_horizon(closed, cols, "xgboost_small", params=params, eval_split="valid", feature_set=fs)
        metrics = consolidation.metric_row_with_topk(valid, "probability_score") if not valid.empty else {}
        row = {"config_id": i, "feature_set": fs, **params, **{f"valid_{k}": v for k, v in metrics.items()}}
        rows.append(row)
        key = (row.get("valid_ece", float("inf")), row.get("valid_brier", float("inf")), -row.get("valid_auc", -float("inf")))
        if key < best_key:
            best_key = key
            best = {"config_id": i, "feature_set": fs, **params}
    if best is None:
        best = {"config_id": 0, "feature_set": fs, "n_estimators": 80, "max_depth": 3, "learning_rate": 0.1, "subsample": 1.0, "colsample_bytree": 0.9, "min_child_weight": 1, "reg_lambda": 1, "reg_alpha": 0}
    valid = consolidation.train_model_by_horizon(closed, cols, "xgboost_small", params=best, eval_split="valid", feature_set=fs)
    test = consolidation.train_model_by_horizon(closed, cols, "xgboost_small", params=best, eval_split="test", feature_set=fs)
    test_metrics = consolidation.metric_row_with_topk(test, "probability_score") if not test.empty else {}
    for row in rows:
        row["selected"] = row["config_id"] == best["config_id"]
        if row["selected"]:
            row.update({f"test_{k}": v for k, v in test_metrics.items()})
    selected = pd.concat([valid, test], ignore_index=True) if not valid.empty else test
    return pd.DataFrame(rows), selected, best


def write_coverage_vs_metric_summary(path: Path, ablation: pd.DataFrame, holdout: pd.DataFrame) -> None:
    best = ablation.sort_values(["auc", "ece"], ascending=[False, True]).head(1)
    h_ok = holdout[holdout.get("status", "").eq("ok")] if not holdout.empty and "status" in holdout else pd.DataFrame()
    min_auc = h_ok["auc"].min() if not h_ok.empty and "auc" in h_ok else np.nan
    text = f"""# Coverage Vs Metric Summary

- best feature set: {best.iloc[0]['feature_set'] if not best.empty else ''}
- best AUC: {best.iloc[0]['auc'] if not best.empty and 'auc' in best else np.nan}
- manufacturer holdout min AUC: {min_auc}
- choice-set gain remains small if all_safe_with_choice_set is close to all_safe_without_choice_set.
- selected-subset risk is reduced by coverage expansion but not eliminated.
"""
    (path / "coverage_vs_metric_summary.md").write_text(text, encoding="utf-8")


def run_v2_candidate_policy(root: Path, predictions: pd.DataFrame) -> dict[str, Any]:
    out = root / REPORT_ROOT / "07_candidate_policy_v2"
    out.mkdir(parents=True, exist_ok=True)
    metrics, reco = consolidation.run_candidate_policy_v2(predictions)
    metrics = add_manufacturer_fill_metrics(metrics, predictions)
    metrics.to_csv(out / "candidate_policy_v2_metrics.csv", index=False, encoding="utf-8")
    by_mfg = candidate_policy_by_manufacturer(predictions)
    by_mfg.to_csv(out / "candidate_policy_v2_by_manufacturer.csv", index=False, encoding="utf-8")
    manual = metrics.groupby("candidate_policy", dropna=False).agg(manual_review_load=("manual_review_load", "mean"), candidate_die_recall=("candidate_die_recall", "mean"), candidate_rate=("candidate_rate", "mean")).reset_index()
    manual.to_csv(out / "candidate_policy_v2_manual_load.csv", index=False, encoding="utf-8")
    capacity = manufacturer_worklist_capacity(predictions)
    capacity.to_csv(out / "manufacturer_worklist_capacity_simulation.csv", index=False, encoding="utf-8")
    reco = consolidation.choose_candidate_policy(metrics)
    (out / "candidate_policy_v2_recommendation.md").write_text(render_v2_candidate_recommendation(metrics, reco), encoding="utf-8")
    selected_idx = select_recommended_candidate_rows(predictions, reco.get("candidate_policy", "multi_recall_union_top10"))
    candidate_rows = predictions.loc[selected_idx].copy()
    candidate_rows["candidate_policy"] = reco.get("candidate_policy", "multi_recall_union_top10")
    cand_path = root / DATA_ROOT / "07_candidates" / "candidate_policy_v2_rows.parquet"
    cand_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_rows.to_parquet(cand_path, index=False)
    return {"metrics": metrics, "recommendation": reco, "candidate_rows": candidate_rows, "by_manufacturer": by_mfg}


def add_manufacturer_fill_metrics(metrics: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for policy in ["manufacturer_min_fill", "manufacturer_worklist_fill", "multi_recall_union_top20"]:
        for (horizon, cutoff), group in predictions.groupby(["horizon", "cutoff_period"], dropna=False):
            if policy == "manufacturer_min_fill":
                selected = group.groupby("manufacturer_code", dropna=False, group_keys=False).apply(lambda g: g.sort_values("probability_score", ascending=False).head(min(20, len(g))))
            elif policy == "manufacturer_worklist_fill":
                selected = group.groupby("manufacturer_code", dropna=False, group_keys=False).apply(lambda g: g.sort_values("probability_score", ascending=False).head(min(50, max(20, int(len(g) * 0.05)))))
            else:
                scored = consolidation.add_candidate_policy_scores(group.copy(), str(horizon))
                selected = scored.loc[select_multi_recall_union(scored, 0.20)].copy()
            non = group.drop(index=selected.index, errors="ignore")
            pos = group["label_die_H"].sum()
            rows.append(
                {
                    "candidate_policy": policy,
                    "horizon": horizon,
                    "cutoff_month": cutoff,
                    "full_universe_rows": len(group),
                    "full_universe_die_count": int(pos),
                    "candidate_count": len(selected),
                    "candidate_rate": len(selected) / len(group) if len(group) else np.nan,
                    "candidate_die_count": int(selected["label_die_H"].sum()),
                    "candidate_die_recall": float(selected["label_die_H"].sum() / pos) if pos else np.nan,
                    "candidate_positive_rate": float(selected["label_die_H"].mean()) if len(selected) else np.nan,
                    "non_candidate_positive_rate": float(non["label_die_H"].mean()) if len(non) else np.nan,
                    "lift_vs_non_candidate": float(selected["label_die_H"].mean() / non["label_die_H"].mean()) if len(selected) and len(non) and non["label_die_H"].mean() else np.nan,
                    "precision_at_candidate": float(selected["label_die_H"].mean()) if len(selected) else np.nan,
                    "manual_review_load": len(selected),
                    "manufacturer_coverage": int(selected["manufacturer_code"].nunique()),
                    "stable_segment_coverage": consolidation.stable_segment_rate(selected),
                    "value_coverage": np.nan,
                    "candidate_overlap_with_probability_top10": np.nan,
                    "candidate_unique_reason_distribution": policy,
                }
            )
    return pd.concat([metrics, pd.DataFrame(rows)], ignore_index=True)


def select_recommended_candidate_rows(predictions: pd.DataFrame, policy: str) -> pd.Index:
    selected = pd.Index([])
    for _, group in predictions.groupby(["horizon", "cutoff_period"], dropna=False):
        scored = consolidation.add_candidate_policy_scores(group.copy(), str(group["horizon"].iloc[0]))
        members = consolidation.candidate_policy_members(scored)
        members["multi_recall_union_top20"] = select_multi_recall_union(scored, 0.20)
        selected = selected.union(members.get(policy, members.get("multi_recall_union_top10", pd.Index([]))))
    return selected


def select_multi_recall_union(scored: pd.DataFrame, pct: float) -> pd.Index:
    union = pd.Index([])
    for col in ["probability_rank_score", "interval_rank_score", "frequency_rank_score", "business_priority_score"]:
        if col in scored:
            union = union.union(consolidation.select_top_pct(scored, col, pct, col.replace("_rank_score", "").replace("_score", "")))
    return union


def candidate_policy_by_manufacturer(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (horizon, cutoff, mfg), group in predictions.groupby(["horizon", "cutoff_period", "manufacturer_code"], dropna=False):
        top = group.sort_values("probability_score", ascending=False).head(max(1, int(np.ceil(len(group) * 0.10))))
        rows.append({"horizon": horizon, "cutoff_month": cutoff, "manufacturer_code": mfg, "rows": len(group), "top10_rows": len(top), "top10_positive_rate": float(top["label_die_H"].mean()), "positive_rate": float(group["label_die_H"].mean())})
    return pd.DataFrame(rows)


def manufacturer_worklist_capacity(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cap in [20, 50]:
        for (horizon, cutoff, mfg), group in predictions.groupby(["horizon", "cutoff_period", "manufacturer_code"], dropna=False):
            top = group.sort_values("probability_score", ascending=False).head(min(cap, len(group)))
            rows.append({"capacity_per_manufacturer": cap, "horizon": horizon, "cutoff_month": cutoff, "manufacturer_code": mfg, "worklist_count": len(top), "positive_rate": float(top["label_die_H"].mean()) if len(top) else np.nan})
    return pd.DataFrame(rows)


def render_v2_candidate_recommendation(metrics: pd.DataFrame, reco: dict[str, Any]) -> str:
    summary = metrics.groupby("candidate_policy", dropna=False).agg(candidate_die_recall=("candidate_die_recall", "mean"), candidate_rate=("candidate_rate", "mean"), candidate_positive_rate=("candidate_positive_rate", "mean"), lift_vs_non_candidate=("lift_vs_non_candidate", "mean"), manual_review_load=("manual_review_load", "mean")).reset_index().sort_values("candidate_die_recall", ascending=False)
    return f"""# Candidate Policy V2 Recommendation

- recommended policy: {reco.get("candidate_policy", "")}
- mean candidate die recall: {reco.get("candidate_die_recall", np.nan):.4f}
- mean manual review load: {reco.get("manual_review_load", np.nan):.1f}
- v1 reference recall: 0.4452
- probability_top20 is the controlled-load fallback when union review load is too high.

{summary.to_markdown(index=False)}
"""


def run_v2_probability_gate(root: Path, candidate_rows: pd.DataFrame, *, leakage_clean: bool) -> pd.DataFrame:
    gate = build_probability_availability_gate(candidate_rows, leakage_clean=leakage_clean, selected_subset_caveat=True)
    data_dir = root / DATA_ROOT / "08_service_gate"
    report_dir = root / REPORT_ROOT / "08_service_gate"
    data_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    gate.to_csv(data_dir / "probability_availability_gate.csv", index=False, encoding="utf-8")
    (report_dir / "probability_availability_gate_summary.md").write_text(render_gate_summary(gate), encoding="utf-8")
    (report_dir / "service_gate_decision.md").write_text(render_service_gate_decision(gate), encoding="utf-8")
    return gate


def run_interface_readiness_audit(root: Path, gate: pd.DataFrame) -> dict[str, Any]:
    out = root / REPORT_ROOT / "10_frontend_backend_interface_readiness"
    out.mkdir(parents=True, exist_ok=True)
    design_dir = root / "daily_work" / "notes" / "new_ver" / "前后端设计草案"
    design_parent = root / "daily_work" / "notes" / "new_ver"
    design_dirs = []
    if design_parent.exists():
        design_dirs = [p for p in design_parent.iterdir() if p.is_dir() and ("前后端" in p.name or "设计草案" in p.name)]
    design_dir = design_dirs[0] if design_dirs else design_parent / "前后端设计草案"
    design_parent_candidates = [
        root / "daily_work" / "notes" / "new_ver",
        root.parent / "daily_work" / "notes" / "new_ver",
    ]
    design_parent = next((p for p in design_parent_candidates if p.exists()), design_parent_candidates[0])
    design_dirs = []
    if design_parent.exists():
        design_dirs = [p for p in design_parent.iterdir() if p.is_dir() and ("前后端" in p.name or "设计草案" in p.name)]
    design_dir = design_dirs[0] if design_dirs else design_parent / "前后端设计草案"
    design_files = list(design_dir.glob("*")) if design_dir.exists() else []
    required = [
        "candidate_id",
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "cutoff_month",
        "horizon",
        "churn_probability_H",
        "probability_display_level",
        "display_mode",
        "reason_code",
        "manual_review_required",
        "auto_dispatch_allowed",
    ]
    present = set(gate.columns)
    field_rows = [{"field": f, "available": f in present, "source": "probability_availability_gate"} for f in required]
    fields = pd.DataFrame(field_rows)
    fields.to_csv(out / "required_algorithm_api_fields.csv", index=False, encoding="utf-8")
    fields[~fields["available"]].to_csv(out / "missing_interface_fields.csv", index=False, encoding="utf-8")
    audit = f"""# Interface Readiness Audit

- design draft directory exists: {design_dir.exists()}
- design draft files read-only count: {len(design_files)}
- candidate list available: {not gate.empty}
- worklist available: true
- probability gate available: true
- status decision available: partial via gate display mode
- structured evidence bundle: requires v2 evidence expansion
- forbidden claims: available in model card / gate caveats
- auto_dispatch=false: {bool((gate['auto_dispatch_allowed'] == False).all()) if not gate.empty else True}
- real customer proof-case labels: missing
- organization / salesperson routing: missing
- internal analyst demo: allowed
- customer-facing service: not allowed
"""
    (out / "interface_readiness_audit.md").write_text(audit, encoding="utf-8")
    return {"required_fields": fields, "missing": fields[~fields["available"]], "design_files": design_files}


def write_final_stage_decision(root: Path, model_outputs: dict[str, Any], candidate_outputs: dict[str, Any], gate: pd.DataFrame, interface: dict[str, Any]) -> None:
    out = root / REPORT_ROOT / "09_stage_decision"
    out.mkdir(parents=True, exist_ok=True)
    tuning = model_outputs["tuning"]
    selected = tuning[tuning.get("selected", False).astype(bool)] if "selected" in tuning else pd.DataFrame()
    auc = selected["test_auc"].iloc[0] if not selected.empty and "test_auc" in selected else np.nan
    pr_gain = selected["test_pr_auc_gain"].iloc[0] if not selected.empty and "test_pr_auc_gain" in selected else np.nan
    ece = selected["test_ece"].iloc[0] if not selected.empty and "test_ece" in selected else np.nan
    reco = candidate_outputs["recommendation"]
    text = f"""# Final Stage Decision

- internal_diagnostic_view: true
- analyst_view: true
- proof_case_report: true
- customer_facing_probability_service: false
- auto_dispatch: false

## Key Metrics

- selected model: xgboost_small
- XGBoost AUC / PR-AUC gain / ECE: {auc} / {pr_gain} / {ece}
- recommended M1 policy: {reco.get("candidate_policy", "")}
- M1 recall: {reco.get("candidate_die_recall", np.nan)}
- manual load: {reco.get("manual_review_load", np.nan)}
- probability gate rows: {len(gate)}

Customer-facing probability service remains blocked because this is still a selected subset, probability availability must be enforced at runtime, and choice-set context is partial-platform only.
"""
    (out / "final_stage_decision.md").write_text(text, encoding="utf-8")


def progress(root: Path, message: str, *, reset: bool = False) -> None:
    path = root / PROGRESS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{pd.Timestamp.now().isoformat()} {message}\n"
    if reset:
        path.write_text(line, encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    print(message, flush=True)


__all__ = ["run_entity_complete_v2_coverage_expansion", "TIER_CONFIGS", "VERSION"]
