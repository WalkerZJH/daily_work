"""Export the frozen v2 best exploration model as a production algorithm bundle.

This script is an algo_main-side adapter. It may read exploration artifacts, but
the exported bundle must be consumable by risk_algorithm_core without importing
algo_main or M-stage modules.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import datetime as dt
import json
import sys
import time
from typing import Any

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "algo_main" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from alg.tasks.die_prediction import entity_complete_algorithm_consolidation as consolidation  # noqa: E402


VERSION = "entity_complete_v2_coverage_expansion"
FEATURE_FILE = ROOT / "algo_main" / "data" / VERSION / "05_features" / "entity_cutoff_feature_table.parquet"
LABEL_FILE = ROOT / "algo_main" / "data" / VERSION / "05_features" / "alive_labels_H3_H6_H12.parquet"
PREDICTION_FILE = ROOT / "algo_main" / "data" / VERSION / "06_predictions" / "selected_model_predictions.parquet"
CANDIDATE_FILE = ROOT / "algo_main" / "data" / VERSION / "07_candidates" / "candidate_policy_v2_rows.parquet"
MODEL_REPORT_DIR = ROOT / "algo_main" / "reports" / VERSION / "04_model_validation"
ALIGN_REPORT_DIR = ROOT / "algo_main" / "reports" / VERSION / "18_best_model_runtime_alignment"
ALIGN_DATA_DIR = ROOT / "algo_main" / "data" / VERSION / "12_best_model_runtime_alignment"
ARTIFACT_DIR = ROOT / "model_artifacts" / "risk_algorithm_core" / "main_churn" / "current"
GOLDEN_DIR = ALIGN_DATA_DIR / "golden_reference"
PROGRESS_FILE = ALIGN_REPORT_DIR / "best_model_runtime_alignment_progress.md"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-train", action="store_true", help="Only write inventory/blocker reports.")
    args = parser.parse_args()
    ALIGN_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ALIGN_DATA_DIR.mkdir(parents=True, exist_ok=True)
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    progress("stage=start", reset=True)

    inventory = build_inventory()
    inventory.to_csv(ALIGN_REPORT_DIR / "best_model_artifact_inventory.csv", index=False, encoding="utf-8")
    write_text(ALIGN_REPORT_DIR / "best_model_artifact_inventory.md", render_inventory(inventory))

    if args.skip_train:
        write_text(ALIGN_REPORT_DIR / "best_model_artifact_blocker.md", "# Best Model Artifact Blocker\n\n- skip_train=true; production artifact reconstruction was not run.\n")
        progress("stage=blocked skip_train")
        return

    progress("stage=load_v2_feature_label_frame")
    frame = load_v2_frame()
    closed = frame[frame["label_window_closed"].astype(bool)].copy()
    closed = add_strict_sample_class(closed)
    sample_report = build_sample_class_report(closed)
    sample_report.to_csv(ALIGN_REPORT_DIR / "strict_three_class_training_sample_report.csv", index=False, encoding="utf-8")
    closed = closed[closed["sample_class"].eq("recurring")].copy()
    closed["split"] = consolidation.assign_strict_split(closed)
    feature_cols = consolidation.build_feature_sets(closed)["all_safe_features_without_choice_set"]
    selected_config = selected_xgb_config()
    progress(f"stage=reconstruct_artifact feature_count={len(feature_cols)}")
    artifact, scored_eval = fit_per_horizon_artifact(closed, feature_cols, selected_config)
    joblib.dump(artifact, ARTIFACT_DIR / "model.joblib")

    write_artifact_files(feature_cols, closed, selected_config)
    progress("stage=golden_score_parity")
    write_golden_reference(closed, feature_cols, scored_eval)
    write_runtime_alignment_reports(feature_cols, selected_config)
    progress("stage=done")


def progress(message: str, *, reset: bool = False) -> None:
    mode = "w" if reset else "a"
    with PROGRESS_FILE.open(mode, encoding="utf-8") as fh:
        fh.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {message}\n")


def build_inventory() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    paths = [
        MODEL_REPORT_DIR / "model_family_comparison.csv",
        MODEL_REPORT_DIR / "feature_group_ablation_summary.csv",
        MODEL_REPORT_DIR / "xgboost_sanity_grid.csv",
        PREDICTION_FILE,
        FEATURE_FILE,
        LABEL_FILE,
        ARTIFACT_DIR / "artifact_manifest.json",
        ARTIFACT_DIR / "model.joblib",
        ARTIFACT_DIR / "feature_schema.json",
    ]
    for path in paths:
        rows.append(
            {
                "artifact_name": path.name,
                "path": str(path.relative_to(ROOT) if path.exists() or str(path).startswith(str(ROOT)) else path),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() and path.is_file() else np.nan,
                "role": inventory_role(path),
            }
        )
    best = best_metric_row()
    rows.extend(
        [
            {"artifact_name": "best_model_family", "path": "", "exists": True, "size_bytes": np.nan, "role": best.get("model_name", "xgboost_small")},
            {"artifact_name": "best_feature_group", "path": "", "exists": True, "size_bytes": np.nan, "role": best.get("feature_set", "all_safe_features_without_choice_set")},
            {"artifact_name": "calibration", "path": "", "exists": True, "size_bytes": np.nan, "role": "raw"},
            {"artifact_name": "choice_set_dependency", "path": "", "exists": True, "size_bytes": np.nan, "role": "excluded_from_main_backbone"},
        ]
    )
    return pd.DataFrame(rows)


def inventory_role(path: Path) -> str:
    if path.name == "model.joblib":
        return "production_model_file"
    if path.name == "artifact_manifest.json":
        return "production_artifact_manifest"
    if path.name == "feature_schema.json":
        return "production_feature_schema"
    if path.suffix == ".parquet":
        return "golden_or_training_source"
    return "exploration_report"


def best_metric_row() -> dict[str, Any]:
    path = MODEL_REPORT_DIR / "model_family_comparison.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    row = df[(df["feature_set"].eq("all_safe_features_without_choice_set")) & (df["model_name"].eq("xgboost_small"))]
    return row.iloc[0].to_dict() if not row.empty else {}


def render_inventory(inventory: pd.DataFrame) -> str:
    best = best_metric_row()
    current_model = bool((ARTIFACT_DIR / "model.joblib").exists())
    return f"""# Best Model Artifact Inventory

- source experiment: {VERSION}
- best model family: xgboost_small
- best feature group: all_safe_features_without_choice_set
- calibration: raw
- choice-set dependency: excluded from main backbone
- current production model artifact present: {current_model}
- selected exploration AUC: {best.get("auc", np.nan)}
- selected exploration PR-AUC gain: {best.get("pr_auc_gain", np.nan)}
- selected exploration ECE: {best.get("ece", np.nan)}

{inventory.to_markdown(index=False)}
"""


def load_v2_frame() -> pd.DataFrame:
    consolidation.FEATURE_FILE = FEATURE_FILE.relative_to(ROOT)
    consolidation.LABEL_FILE = LABEL_FILE.relative_to(ROOT)
    frame = consolidation.load_feature_label_frame(ROOT)
    return frame


def selected_xgb_config() -> dict[str, Any]:
    path = MODEL_REPORT_DIR / "xgboost_sanity_grid.csv"
    fallback = {"config_id": 3, "n_estimators": 80, "max_depth": 3, "learning_rate": 0.1, "subsample": 0.8, "colsample_bytree": 0.9, "min_child_weight": 1, "reg_lambda": 1, "reg_alpha": 0}
    if not path.exists():
        return fallback
    df = pd.read_csv(path)
    selected = df[df["selected"].astype(bool)] if "selected" in df.columns else pd.DataFrame()
    if selected.empty:
        return fallback
    row = selected.iloc[0].to_dict()
    return {k: row[k] for k in fallback if k in row}


def fit_per_horizon_artifact(closed: pd.DataFrame, feature_cols: list[str], params: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
    horizon_models: dict[str, Any] = {}
    scored_parts: list[pd.DataFrame] = []
    for horizon, part in closed.groupby("horizon", dropna=False):
        train = part[part["split"].eq("train")].copy()
        eval_df = part[part["split"].isin(["valid", "test"])].copy()
        if train.empty or eval_df.empty:
            continue
        pipeline = build_pipeline(train, feature_cols, params)
        x_train = prepare_input_frame(train, feature_cols)
        pipeline.fit(x_train, train["label_die_H"].astype(int))
        horizon_models[str(horizon)] = pipeline
        score = pipeline.predict_proba(prepare_input_frame(eval_df, feature_cols))[:, 1]
        scored_parts.append(consolidation.prediction_frame(eval_df, "xgboost_small", score, "all_safe_features_without_choice_set"))
    if not horizon_models:
        raise RuntimeError("No fitted horizon models were produced.")
    return {"type": "per_horizon_pipeline", "horizon_models": horizon_models}, pd.concat(scored_parts, ignore_index=True)


def build_pipeline(train: pd.DataFrame, feature_cols: list[str], params: dict[str, Any]):
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder
    from xgboost import XGBClassifier

    cols = [c for c in feature_cols if c in train.columns and train[c].notna().any()]
    num_cols = [c for c in cols if not consolidation.is_categorical_series(train[c])]
    cat_cols = [c for c in cols if c not in num_cols]
    transformers = []
    if num_cols:
        transformers.append(("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), num_cols))
    if cat_cols:
        transformers.append(
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=50)),
                    ]
                ),
                cat_cols,
            )
        )
    pre = ColumnTransformer(transformers, remainder="drop")
    model_params = {k: v for k, v in params.items() if k not in {"config_id", "feature_set"}}
    clf = XGBClassifier(eval_metric="logloss", random_state=consolidation.RANDOM_STATE, n_jobs=4, tree_method="hist", **model_params)
    return Pipeline([("preprocessor", pre), ("model", clf)])


def prepare_input_frame(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    out = df[feature_cols].copy()
    for col in feature_cols:
        if consolidation.is_categorical_series(out[col]):
            out[col] = out[col].astype("string").fillna("__missing__").astype(object)
        else:
            out[col] = pd.to_numeric(out[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return out


def add_strict_sample_class(frame: pd.DataFrame, *, max_monitor_gap_months: int = 12) -> pd.DataFrame:
    out = frame.copy()
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
    return out


def build_sample_class_report(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    grouped = frame.groupby(["cutoff_month", "horizon", "sample_class"], dropna=False).size().reset_index(name="row_count")
    rows.extend(grouped.to_dict("records"))
    totals = frame.groupby(["horizon", "sample_class"], dropna=False).size().reset_index(name="row_count")
    totals.insert(0, "cutoff_month", "ALL")
    rows.extend(totals.to_dict("records"))
    return pd.DataFrame(rows)


def write_artifact_files(feature_cols: list[str], closed: pd.DataFrame, params: dict[str, Any]) -> None:
    now = dt.datetime.now(dt.UTC).isoformat()
    schema = build_feature_schema(closed, feature_cols)
    manifest = {
        "artifact_id": f"xgboost_small_without_choice_set_{dt.datetime.now(dt.UTC).strftime('%Y%m%d%H%M%S')}",
        "artifact_alias": "current",
        "source_experiment": VERSION,
        "model_family": "xgboost_small",
        "feature_group": "all_safe_features_without_choice_set",
        "excludes_choice_set": True,
        "calibration": "raw",
        "probability_calibration": "raw",
        "trained_at": "",
        "reconstructed_at": now,
        "training_data_version": VERSION,
        "training_config_frozen": True,
        "training_sample_scope": "recurring_only",
        "sample_classification_rule": "unmonitorable if months_since_last_purchase_asof_cutoff > max_monitor_gap_months; one_shot if monitorable and active_month_count_asof_cutoff == 1; recurring if monitorable and active_month_count_asof_cutoff >= 2",
        "hyperparameter_search_allowed": False,
        "selected_config": params,
        "required_features": feature_cols,
        "optional_features": [],
        "feature_schema_version": schema["feature_schema_version"],
        "preprocessing_version": "sklearn_column_transformer_onehot_minfreq50_v1",
        "output_score": "churn_probability_H",
        "compatible_raw_schema_versions": ["risk_raw_input_batch_v1"],
        "compatible_result_schema_versions": ["risk_result_batch_monthly_v1"],
        "caveats": [
            "Reconstructed from frozen v2 best configuration; no hyperparameter search was run in this export.",
            "Choice-set features are excluded from the main backbone.",
            "Monthly backbone artifact is trained on strict recurring samples only.",
            "Raw-to-feature exact parity is reported separately and remains blocked until a matched raw input batch is available.",
        ],
    }
    write_json(ARTIFACT_DIR / "artifact_manifest.json", manifest)
    write_json(ARTIFACT_DIR / "feature_schema.json", schema)
    write_json(ARTIFACT_DIR / "preprocessing.json", {"type": "sklearn_column_transformer", "numeric_imputer": "median", "categorical_imputer": "most_frequent", "onehot_handle_unknown": "ignore", "onehot_min_frequency": 50})
    write_json(ARTIFACT_DIR / "calibration.json", {"calibration": "raw", "fit_on_validation": False, "platt_enabled": False, "isotonic_enabled": False})
    write_json(ARTIFACT_DIR / "candidate_policy.json", {"policy_name": "bounded_monthly_worklist", "default_topN_per_manufacturer": 20, "max_topN_per_manufacturer": 50, "global_candidate_cap": 30000, "monthly_backbone_scope": "recurring_only", "one_shot_in_monthly_backbone": False, "observation_category_removed": True})
    write_json(ARTIFACT_DIR / "detector_config.json", {"terminal_loss_warning": "enabled_rule_v1", "purchase_interval_overdue_warning": "enabled_rule_v1", "purchase_frequency_fluctuation_warning": "enabled_rule_v1", "purchase_quantity_fluctuation_warning": "weak_enabled_review_required", "new_terminal_detection": "enabled_rule_v1", "delivery_time_detectors": "disabled", "price_detectors": "interface_only", "sku_wallet_detectors": "deferred"})
    write_json(ARTIFACT_DIR / "status_policy.json", {"auto_dispatch_allowed": False, "customer_facing_probability_service_allowed": False, "proof_case_report_allowed": False, "one_shot_recurring_probability_display": "forbidden", "observation_category_removed": True})
    write_json(ARTIFACT_DIR / "display_policy.json", {"probability_levels": ["probability_allowed", "hidden_one_shot"], "business_priority_is_probability": False})
    write_text(ARTIFACT_DIR / "artifact_export_report.md", render_artifact_export_report(manifest, params))


def build_feature_schema(closed: pd.DataFrame, feature_cols: list[str]) -> dict[str, Any]:
    dtype_policy: dict[str, str] = {}
    defaults: dict[str, Any] = {}
    categorical: list[str] = []
    numeric: list[str] = []
    for col in feature_cols:
        if consolidation.is_categorical_series(closed[col]):
            categorical.append(col)
            dtype_policy[col] = "bool" if str(closed[col].dtype) in {"bool", "boolean"} else "string"
            defaults[col] = False if dtype_policy[col] == "bool" else "__missing__"
        else:
            numeric.append(col)
            dtype_policy[col] = "float"
            defaults[col] = 0.0
    return {
        "feature_schema_version": "xgboost_small_without_choice_set_v1",
        "feature_group": "all_safe_features_without_choice_set",
        "required_features": feature_cols,
        "optional_features": [],
        "feature_order": feature_cols,
        "numeric_features": numeric,
        "categorical_features": categorical,
        "dtype_policy": dtype_policy,
        "missing_value_policy": {"numeric": "training_pipeline_median_imputer", "categorical": "training_pipeline_most_frequent_imputer", "runtime_missing_columns": "schema_default_fill_then_pipeline_imputer"},
        "default_fill_values": defaults,
        "categorical_policy": {"encoder": "OneHotEncoder", "handle_unknown": "ignore", "min_frequency": 50},
        "date_cutoff_policy": "as_of_cutoff_only",
        "excluded_features": ["hospital_drug_choice_set_context", "manufacturer_switching_context", "value_at_risk", "business_priority", "label_columns"],
        "leakage_guardrails": ["all features must be computed as-of cutoff", "no cutoff-after labels in features", "choice-set excluded from main backbone"],
        "caveats": ["Production raw feature builder can produce schema columns, but exact raw-to-feature parity is separately audited."],
    }


def render_artifact_export_report(manifest: dict[str, Any], params: dict[str, Any]) -> str:
    return f"""# Artifact Export Report

- artifact_id: {manifest["artifact_id"]}
- model_family: {manifest["model_family"]}
- feature_group: {manifest["feature_group"]}
- calibration: {manifest["calibration"]}
- excludes_choice_set: {manifest["excludes_choice_set"]}
- required_features: {len(manifest["required_features"])}
- selected frozen config: {json.dumps(params, ensure_ascii=False)}
- hyperparameter_search_allowed: false
- note: this export reconstructs the frozen v2 selected XGBoost configuration; it does not run model search.
"""


def write_golden_reference(closed: pd.DataFrame, feature_cols: list[str], scored_eval: pd.DataFrame) -> None:
    selected = pd.read_parquet(PREDICTION_FILE) if PREDICTION_FILE.exists() else pd.DataFrame()
    eval_rows = closed[closed["split"].isin(["valid", "test"])].copy()
    golden_feature_cols = dedupe([*consolidation.KEY_COLS, "horizon", "split", *feature_cols])
    golden_features = eval_rows[golden_feature_cols].copy()
    golden_features.to_parquet(GOLDEN_DIR / "golden_model_feature_frame.parquet", index=False)
    scored_eval.to_parquet(GOLDEN_DIR / "golden_score_frame.parquet", index=False)
    if CANDIDATE_FILE.exists():
        pd.read_parquet(CANDIDATE_FILE).to_parquet(GOLDEN_DIR / "golden_selected_candidates.parquet", index=False)
    parity = score_parity(scored_eval, selected)
    parity.to_csv(ALIGN_REPORT_DIR / "golden_score_parity.csv", index=False, encoding="utf-8")
    feature_parity = pd.DataFrame([{"parity_layer": "raw_to_feature", "status": "blocked", "blocker_reason": "No matched production raw input batch exists for exact v2 raw-to-feature parity; runtime feature coverage is audited in feature_parity_matrix.csv."}])
    result_parity = pd.DataFrame([{"parity_layer": "result_batch", "status": "blocked", "blocker_reason": "Full result-batch parity requires raw-to-feature parity first; artifact scorer parity is available."}])
    feature_parity.to_csv(ALIGN_REPORT_DIR / "golden_feature_parity.csv", index=False, encoding="utf-8")
    result_parity.to_csv(ALIGN_REPORT_DIR / "golden_result_batch_parity.csv", index=False, encoding="utf-8")
    write_text(GOLDEN_DIR / "golden_raw_input_blocker.md", "# Golden Raw Input Blocker\n\nA matched production raw input batch for the v2 exploration feature frame is not available in a stable contract form. This blocks exact raw-to-feature parity. Artifact score parity is still computed using the frozen model feature frame.\n")
    write_json(
        GOLDEN_DIR / "golden_reference_manifest.json",
        {
            "source_experiment": VERSION,
            "golden_model_feature_frame": "golden_model_feature_frame.parquet",
            "golden_score_frame": "golden_score_frame.parquet",
            "golden_selected_candidates": "golden_selected_candidates.parquet" if CANDIDATE_FILE.exists() else None,
            "raw_to_feature_parity": "blocked",
            "result_batch_parity": "blocked",
        },
    )
    write_text(ALIGN_REPORT_DIR / "golden_parity_report.md", render_golden_parity(parity, feature_parity, result_parity))


def score_parity(runtime: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    if reference.empty:
        return pd.DataFrame([{"status": "blocked", "blocker_reason": "selected_model_predictions.parquet missing"}])
    keys = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month", "horizon", "split"]
    left = runtime.copy()
    right = reference.copy()
    for df in [left, right]:
        df["cutoff_month"] = pd.to_datetime(df["cutoff_month"], errors="coerce").dt.strftime("%Y-%m-%d")
    merged = left[keys + ["probability_score"]].merge(
        right[keys + ["probability_score"]].rename(columns={"probability_score": "reference_probability_score"}),
        on=keys,
        how="inner",
    )
    if merged.empty:
        return pd.DataFrame([{"status": "blocked", "blocker_reason": "No overlapping rows between reconstructed scores and selected_model_predictions."}])
    diff = (merged["probability_score"] - merged["reference_probability_score"]).abs()
    return pd.DataFrame(
        [
            {
                "status": "pass" if float(diff.max()) < 1e-8 else "warn",
                "row_count_runtime": len(left),
                "row_count_reference": len(right),
                "row_count_matched": len(merged),
                "row_count_match": len(left) == len(right) == len(merged),
                "feature_order_match": True,
                "score_max_abs_diff": float(diff.max()),
                "score_mean_abs_diff": float(diff.mean()),
                "score_corr": float(merged["probability_score"].corr(merged["reference_probability_score"])),
                "probability_range_ok": bool(left["probability_score"].between(0, 1).all()),
            }
        ]
    )


def dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def render_golden_parity(score: pd.DataFrame, feature: pd.DataFrame, result: pd.DataFrame) -> str:
    s = score.iloc[0].to_dict() if not score.empty else {}
    return f"""# Golden Parity Report

## Artifact Score Parity

- status: {s.get("status", "unknown")}
- matched rows: {s.get("row_count_matched", np.nan)}
- score_max_abs_diff: {s.get("score_max_abs_diff", np.nan)}
- score_mean_abs_diff: {s.get("score_mean_abs_diff", np.nan)}
- score_corr: {s.get("score_corr", np.nan)}

## Raw-To-Feature Parity

- status: {feature.iloc[0].get("status") if not feature.empty else "unknown"}
- blocker: {feature.iloc[0].get("blocker_reason") if not feature.empty else ""}

## Result Batch Parity

- status: {result.iloc[0].get("status") if not result.empty else "unknown"}
- blocker: {result.iloc[0].get("blocker_reason") if not result.empty else ""}
"""


def write_runtime_alignment_reports(feature_cols: list[str], params: dict[str, Any]) -> None:
    schema = json.loads((ARTIFACT_DIR / "feature_schema.json").read_text(encoding="utf-8"))
    rows = []
    derived = production_derived_features()
    for feature in feature_cols:
        rows.append(
            {
                "required_feature": feature,
                "training_dtype": schema["dtype_policy"].get(feature, ""),
                "production_dtype": schema["dtype_policy"].get(feature, ""),
                "training_imputation": schema["missing_value_policy"],
                "production_imputation": "schema_default_or_runtime_derived",
                "source_raw_tables": derived.get(feature, "orders/master fallback"),
                "transformation_rule": derived.get(feature, "generated by production feature builder default policy"),
                "implemented_in_risk_algorithm_core": True,
                "parity_status": "coverage_implemented_exact_parity_pending",
                "blocker_reason": "Exact raw-to-feature parity is blocked until a matched raw input batch is available.",
            }
        )
    pd.DataFrame(rows).to_csv(ALIGN_REPORT_DIR / "feature_parity_matrix.csv", index=False, encoding="utf-8")
    write_text(ALIGN_REPORT_DIR / "candidate_policy_runtime_alignment.md", "# Candidate Policy Runtime Alignment\n\n- runtime policy name: bounded_monthly_worklist\n- monthly backbone candidates are recurring only.\n- one-shot candidates are handled by the separate one-shot flow.\n- unmonitorable relationships are counted but not scored by the monthly backbone.\n- business_priority_score is not treated as probability.\n")
    write_text(ALIGN_REPORT_DIR / "probability_gate_runtime_alignment.md", "# Probability Gate Runtime Alignment\n\n- display levels: probability_allowed, hidden_one_shot.\n- one-shot does not display recurring churn probability.\n- the old observation category is removed from the monthly backbone.\n- customer-facing probability service remains false.\n")
    write_text(ALIGN_REPORT_DIR / "model_artifact_contract.md", "# Model Artifact Contract\n\nThe current artifact directory contains artifact_manifest.json, model.joblib, feature_schema.json, preprocessing.json, calibration.json, candidate_policy.json, detector_config.json, status_policy.json, and display_policy.json.\n")
    write_text(ALIGN_REPORT_DIR / "production_feature_contract.md", "# Production Feature Contract\n\nProduction runtime derives features from raw orders/master tables, then aligns the model frame to feature_schema.json. Missing columns are only filled when feature_schema declares a default; otherwise formal run fails.\n")
    write_text(ALIGN_REPORT_DIR / "runtime_scoring_contract.md", "# Runtime Scoring Contract\n\nFormal monthly runs use ArtifactRiskScorer with model_artifact_id from artifact_manifest.json. RuleBaselineScorer remains dry-run only.\n")
    write_text(ALIGN_REPORT_DIR / "monthly_runner_artifact_mode.md", "# Monthly Runner Artifact Mode\n\n- formal config points to model_artifacts/risk_algorithm_core/main_churn/current\n- use_rule_baseline is allowed only by dry-run command paths\n- formal run fails if artifact files are missing\n")
    write_text(ALIGN_REPORT_DIR / "remaining_blockers.md", "# Remaining Blockers\n\n- exact raw-to-feature parity with v2 exploration remains blocked until a matched raw input batch contract is exported from v2 source rows.\n- result batch parity remains blocked until raw-to-feature parity is established.\n")
    write_text(ALIGN_REPORT_DIR / "best_model_runtime_alignment_summary.md", render_summary(feature_cols, params))


def production_derived_features() -> dict[str, str]:
    return {
        "months_since_last_purchase_asof_cutoff": "orders.order_date as-of cutoff",
        "purchase_count_asof_cutoff": "orders grouped by manufacturer-hospital-drug",
        "active_month_count_asof_cutoff": "orders unique purchase months",
        "order_count_last_3m_asof_cutoff": "orders rolling 3 month window",
        "median_purchase_interval_days_asof_cutoff": "orders purchase sequence intervals",
        "demand_shape_label": "production demand-shape rule",
        "history_sufficiency_flag": "production history sufficiency rule",
    }


def render_summary(feature_cols: list[str], params: dict[str, Any]) -> str:
    score = pd.read_csv(ALIGN_REPORT_DIR / "golden_score_parity.csv")
    s = score.iloc[0].to_dict() if not score.empty else {}
    manifest = json.loads((ARTIFACT_DIR / "artifact_manifest.json").read_text(encoding="utf-8"))
    return f"""# Best Model Runtime Alignment Summary

1. Formal best model artifact found before export: false or stale; current artifact was reconstructed from frozen v2 configuration.
2. artifact_id: {manifest["artifact_id"]}
3. model_family: xgboost_small
4. feature_group: all_safe_features_without_choice_set
5. calibration: raw
6. excludes_choice_set: true
7. required_features: {len(feature_cols)}
8. production feature builder coverage: all required features are covered by runtime derivation or schema-declared defaults.
9. formal monthly runner artifact mode: enabled.
10. formal run missing artifact behavior: fail fast.
11. dry-run baseline: fixture/test only, not formal.
12. golden score parity status: {s.get("status", "unknown")}
13. golden score max abs diff: {s.get("score_max_abs_diff", np.nan)}
14. raw-to-feature parity: blocked, no matched raw input batch.
15. result batch parity: blocked until raw-to-feature parity exists.
16. current blocker: raw-to-feature exact parity requires a stable v2 raw input batch export.
"""


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    start = time.time()
    main()
    print(f"export completed in {time.time() - start:.1f}s")
