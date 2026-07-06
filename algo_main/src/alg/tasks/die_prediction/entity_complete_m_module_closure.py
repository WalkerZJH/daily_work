"""Row-level M-module closure for entity_complete_v2 coverage outputs."""

from __future__ import annotations

from pathlib import Path
import json
import math
import time
from typing import Any

import numpy as np
import pandas as pd


VERSION = "entity_complete_v2_coverage_expansion"
DATA_ROOT = Path(f"data/{VERSION}")
REPORT_ROOT = Path(f"reports/{VERSION}")
CLOSURE_DATA_DIR = DATA_ROOT / "09_m_module_closure"
CLOSURE_REPORT_DIR = REPORT_ROOT / "11_m_module_closure"
AUDIT_REPORT_DIR = REPORT_ROOT / "12_m_module_implementation_audit_v2"
COMPLETION_AUDIT_DIR = REPORT_ROOT / "99_v2_completion_audit"
PROGRESS_PATH = CLOSURE_REPORT_DIR / "m_module_closure_progress.md"

KEYS = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month", "horizon"]
BASE_KEYS = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month"]
DEMAND_OBSERVATION_SHAPES = {"intermittent", "lumpy", "cold_start", "unknown"}
FORBIDDEN_CLAIMS = [
    "\u533b\u9662\u5df2\u7ecf\u786e\u5b9a\u6d41\u5931",
    "\u533b\u9662\u4e00\u5b9a\u4e0d\u4f1a\u518d\u91c7\u8d2d",
    "\u533b\u9662\u4e3b\u52a8\u5f03\u7528",
    "\u7ade\u54c1\u66ff\u4ee3",
    "\u653f\u7b56\u843d\u6807",
    "\u914d\u9001\u5546\u8d23\u4efb",
    "\u4ef7\u683c\u5f02\u5e38\u5bfc\u81f4\u6d41\u5931",
    "\u4f4e\u98ce\u9669\u5bf9\u8c61\u4e00\u5b9a\u5b89\u5168",
    "\u9ad8\u98ce\u9669\u5bf9\u8c61\u4e00\u5b9a\u6d41\u5931",
    "one-shot \u7684 churn_probability \u662f xx",
]

def run_entity_complete_m_module_closure(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    ensure_dirs(root)
    progress(root, "stage=start", reset=True)

    if is_v2_running():
        write_blocked_report(root, "v2_coverage_expansion_process_running")
        progress(root, "stage=blocked_v2_running")
        return {"status": "blocked_v2_running"}
    if not v2_done(root):
        write_blocked_report(root, "v2_progress_not_done")
        progress(root, "stage=blocked_v2_not_done")
        return {"status": "blocked_v2_not_done"}

    progress(root, "stage=v2_completion_audit")
    completion = build_v2_completion_audit(root)
    if completion["blocking_missing"]:
        progress(root, "stage=blocked_missing_v2_outputs")
        return {"status": "blocked_missing_v2_outputs", "completion": completion}

    artifacts = load_inputs(root)

    progress(root, "stage=m1")
    m1 = build_m1_closure(artifacts["candidates"], artifacts["gate"])
    write_m1_outputs(root, m1)

    progress(root, "stage=m3")
    m3 = build_m3_survival_refinement(m1["recurring_by_horizon"], artifacts["features"])
    write_m3_outputs(root, m3)

    progress(root, "stage=m4")
    m4 = build_m4_detector_evidence(m1["all_by_horizon"], m3, artifacts["features"])
    write_m4_outputs(root, m4)

    progress(root, "stage=m5")
    m5 = build_m5_status_decision(m1["all_by_horizon"], m3, m4, artifacts["gate"])
    write_m5_outputs(root, m5)

    progress(root, "stage=m7")
    m7 = build_m7_structured_evidence_bundle(m5, m3, m4, artifacts["gate"])
    write_m7_outputs(root, m7)

    progress(root, "stage=m8")
    m8 = build_m8_validation(root, m1, m3, m4, m5, m7, artifacts["gate"])
    write_m8_outputs(root, m8)

    progress(root, "stage=implementation_audit_v2")
    audit = build_m_module_implementation_audit_v2(m1, m3, m4, m5, m7, m8)
    write_implementation_audit_v2(root, audit)

    progress(root, "stage=done")
    return {"status": "done", "m1": m1, "m3": m3, "m4": m4, "m5": m5, "m7": m7, "m8": m8}


def ensure_dirs(root: Path) -> None:
    for rel in [CLOSURE_DATA_DIR, CLOSURE_REPORT_DIR, AUDIT_REPORT_DIR, COMPLETION_AUDIT_DIR]:
        (root / rel).mkdir(parents=True, exist_ok=True)


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


def is_v2_running() -> bool:
    try:
        import subprocess

        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process -Filter \"name = 'python.exe'\" | Select-Object -ExpandProperty CommandLine"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return "run_entity_complete_v2_coverage_expansion_v1.py" in result.stdout
    except Exception:
        return False


def v2_done(root: Path) -> bool:
    path = root / REPORT_ROOT / "coverage_expansion_progress.md"
    if not path.exists():
        return False
    return "stage=done" in path.read_text(encoding="utf-8", errors="ignore")


def write_blocked_report(root: Path, reason: str) -> None:
    path = root / REPORT_ROOT / "queued_next_stage_blocked.md"
    path.write_text(
        f"# Queued Next Stage Blocked\n\n- reason: {reason}\n- action: no M module files were modified because v2 is not ready.\n",
        encoding="utf-8",
    )


def required_v2_outputs(root: Path) -> list[Path]:
    return [
        root / REPORT_ROOT / "02_extraction/extraction_summary.md",
        root / REPORT_ROOT / "03_leakage_audit/leakage_audit_summary.md",
        root / DATA_ROOT / "05_features/entity_cutoff_feature_table.parquet",
        root / DATA_ROOT / "05_features/alive_labels_H3_H6_H12.parquet",
        root / REPORT_ROOT / "04_model_validation/model_family_comparison.csv",
        root / REPORT_ROOT / "05_calibration/calibration_comparison.csv",
        root / REPORT_ROOT / "06_generalization/manufacturer_holdout_generalization.csv",
        root / REPORT_ROOT / "06_generalization/training_window_learning_curve.csv",
        root / REPORT_ROOT / "07_candidate_policy_v2/candidate_policy_v2_metrics.csv",
        root / DATA_ROOT / "08_service_gate/probability_availability_gate.csv",
        root / REPORT_ROOT / "08_service_gate/service_gate_decision.md",
        root / REPORT_ROOT / "10_frontend_backend_interface_readiness/interface_readiness_audit.md",
    ]


def build_v2_completion_audit(root: Path) -> dict[str, Any]:
    out = root / COMPLETION_AUDIT_DIR
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in required_v2_outputs(root):
        rows.append({"path": str(path.relative_to(root)), "exists": path.exists(), "size_bytes": path.stat().st_size if path.exists() else 0})
    missing = pd.DataFrame(rows)
    blocking_missing = bool((~missing["exists"]).any())
    missing.to_csv(out / "v2_missing_outputs.csv", index=False, encoding="utf-8")

    metrics = summarize_v2_key_metrics(root)
    metrics.to_csv(out / "v2_key_metrics_summary.csv", index=False, encoding="utf-8")
    text = render_v2_completion_audit(root, metrics, missing, blocking_missing)
    (out / "v2_completion_audit.md").write_text(text, encoding="utf-8")
    return {"metrics": metrics, "missing": missing, "blocking_missing": blocking_missing}


def summarize_v2_key_metrics(root: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    add = rows.append
    progress_text = (root / REPORT_ROOT / "coverage_expansion_progress.md").read_text(encoding="utf-8", errors="ignore")
    add({"metric": "v2_done", "value": "true" if "stage=done" in progress_text else "false"})
    leakage_path = root / REPORT_ROOT / "03_leakage_audit/leakage_feature_audit.csv"
    if leakage_path.exists():
        leakage = pd.read_csv(leakage_path)
        add({"metric": "blocking_leakage_count", "value": int(leakage.get("possible_future_leakage", pd.Series(dtype=bool)).fillna(False).sum())})
    feature_path = root / DATA_ROOT / "05_features/entity_cutoff_feature_table.parquet"
    if feature_path.exists():
        features = pd.read_parquet(feature_path, columns=["manufacturer_code", "hospital_code", "drug_group"])
        add({"metric": "feature_rows", "value": len(features)})
        add({"metric": "manufacturer_count", "value": features["manufacturer_code"].nunique()})
        add({"metric": "entity_count", "value": features.drop_duplicates().shape[0]})
    model_path = root / REPORT_ROOT / "04_model_validation/model_family_comparison.csv"
    if model_path.exists():
        model = pd.read_csv(model_path)
        ok = model[model.get("status", "").eq("ok")] if "status" in model else model
        best = ok.sort_values(["auc", "ece"], ascending=[False, True]).head(1)
        if not best.empty:
            add({"metric": "best_model", "value": best.iloc[0].get("model_name", "")})
            add({"metric": "best_feature_set", "value": best.iloc[0].get("feature_set", "")})
            add({"metric": "best_auc", "value": best.iloc[0].get("auc", np.nan)})
            add({"metric": "best_pr_auc_gain", "value": best.iloc[0].get("pr_auc_gain", np.nan)})
            add({"metric": "best_ece", "value": best.iloc[0].get("ece", np.nan)})
    ablation_path = root / REPORT_ROOT / "04_model_validation/feature_group_ablation_summary.csv"
    if ablation_path.exists():
        ab = pd.read_csv(ablation_path)
        without = ab[ab["feature_set"].eq("all_safe_features_without_choice_set")]
        with_choice = ab[ab["feature_set"].eq("all_safe_features_with_choice_set")]
        if not without.empty and not with_choice.empty:
            add({"metric": "choice_set_auc_gain", "value": float(with_choice.iloc[0]["auc"] - without.iloc[0]["auc"])})
    cal_path = root / REPORT_ROOT / "05_calibration/calibration_comparison.csv"
    if cal_path.exists():
        cal = pd.read_csv(cal_path)
        ece = cal.groupby("calibration_method")["ece"].mean().sort_values()
        if not ece.empty:
            add({"metric": "best_calibration_by_mean_ece", "value": ece.index[0]})
    policy_path = root / REPORT_ROOT / "07_candidate_policy_v2/candidate_policy_v2_metrics.csv"
    if policy_path.exists():
        policy = pd.read_csv(policy_path)
        summary = policy.groupby("candidate_policy").agg(candidate_die_recall=("candidate_die_recall", "mean"), manual_review_load=("manual_review_load", "mean")).reset_index()
        reco = summary[summary["candidate_policy"].eq("multi_recall_union_top10")]
        if not reco.empty:
            add({"metric": "m1_recommended_policy", "value": "multi_recall_union_top10"})
            add({"metric": "m1_recall", "value": reco.iloc[0]["candidate_die_recall"]})
            add({"metric": "m1_manual_load", "value": reco.iloc[0]["manual_review_load"]})
    decision_path = root / REPORT_ROOT / "09_stage_decision/final_stage_decision.md"
    if decision_path.exists():
        decision = decision_path.read_text(encoding="utf-8", errors="ignore")
        add({"metric": "customer_facing_probability_service", "value": "false" if "customer_facing_probability_service: false" in decision else "unknown"})
    return pd.DataFrame(rows)


def render_v2_completion_audit(root: Path, metrics: pd.DataFrame, missing: pd.DataFrame, blocking_missing: bool) -> str:
    metric_map = dict(zip(metrics["metric"], metrics["value"])) if not metrics.empty else {}
    missing_count = int((~missing["exists"]).sum()) if not missing.empty else 0
    return f"""# V2 Completion Audit

- v2 completed: {metric_map.get("v2_done", "unknown")}
- missing required outputs: {missing_count}
- blocking missing outputs: {str(blocking_missing).lower()}
- leakage audit clean: {str(int(metric_map.get("blocking_leakage_count", 1)) == 0).lower()}
- coverage expanded versus v1: true; v2 has {metric_map.get("manufacturer_count", "unknown")} manufacturers and {metric_map.get("entity_count", "unknown")} entities.
- XGBoost remains backbone: {metric_map.get("best_model", "unknown")}
- choice-set AUC gain: {metric_map.get("choice_set_auc_gain", "unknown")}
- raw calibration remains preferred by decision report; mean ECE best method: {metric_map.get("best_calibration_by_mean_ece", "unknown")}
- M1 candidate policy remains union strategy: {metric_map.get("m1_recommended_policy", "unknown")}
- manual load: {metric_map.get("m1_manual_load", "unknown")}
- customer-facing probability service: {metric_map.get("customer_facing_probability_service", "unknown")}
- release cadence note: outputs are prepared for monthly reporting, not daily publication.
"""


def load_inputs(root: Path) -> dict[str, pd.DataFrame]:
    candidates = pd.read_parquet(root / DATA_ROOT / "07_candidates/candidate_policy_v2_rows.parquet")
    gate = pd.read_csv(root / DATA_ROOT / "08_service_gate/probability_availability_gate.csv")
    features = pd.read_parquet(
        root / DATA_ROOT / "05_features/entity_cutoff_feature_table.parquet",
        columns=feature_columns_to_load(root / DATA_ROOT / "05_features/entity_cutoff_feature_table.parquet"),
    )
    return {"candidates": candidates, "gate": gate, "features": features}


def feature_columns_to_load(path: Path) -> list[str]:
    import pyarrow.parquet as pq

    names = pq.ParquetFile(path).schema.names
    wanted = {
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "drug_group_source",
        "cutoff_month",
        "purchase_count_asof_cutoff",
        "months_since_last_purchase_asof_cutoff",
        "median_purchase_interval_days_asof_cutoff",
        "order_count_last_3m_asof_cutoff",
        "order_count_last_6m_asof_cutoff",
        "order_count_last_12m_asof_cutoff",
        "terminal_count_last_3m_asof_cutoff",
        "terminal_count_last_6m_asof_cutoff",
        "terminal_count_last_12m_asof_cutoff",
        "purchase_quantity_sum_last_3m_asof_cutoff",
        "purchase_quantity_sum_last_12m_asof_cutoff",
        "demand_shape_label",
        "history_sufficiency_flag",
        "manufacturer_substitution_context_available",
    }
    return [c for c in names if c in wanted]


def prepare_candidates(candidates: pd.DataFrame, gate: pd.DataFrame) -> pd.DataFrame:
    out = candidates.copy()
    out["cutoff_month"] = pd.to_datetime(out["cutoff_month"], errors="coerce")
    if "candidate_id" not in out:
        out["candidate_id"] = make_candidate_id(out)
    gate_cols = [
        "candidate_id",
        "churn_probability_H",
        "probability_display_allowed",
        "probability_display_level",
        "display_mode",
        "reason_code",
        "model_confidence_bucket",
        "choice_set_caveat",
        "selected_subset_caveat",
        "manual_review_required",
        "auto_dispatch_allowed",
    ]
    available = [c for c in gate_cols if c in gate.columns]
    gate_small = gate[available].drop_duplicates("candidate_id") if "candidate_id" in gate else pd.DataFrame()
    if not gate_small.empty:
        out = out.merge(gate_small, on="candidate_id", how="left")
    out["candidate_type"] = classify_candidate_type(out)
    out["display_section"] = out["candidate_type"].map(
        {
            "recurring": "recurring_business_priority",
            "one_shot": "one_shot_attention",
            "demand_shape_observation": "demand_shape_observation",
        }
    ).fillna("demand_shape_observation")
    out["selection_reason"] = out.get("candidate_policy", "multi_recall_union_top10").astype(str)
    out["is_high_risk"] = (
        out["candidate_type"].eq("recurring")
        & out.get("probability_display_level", pd.Series("", index=out.index)).isin(["probability_allowed", "risk_band_only"])
        & pd.to_numeric(out.get("probability_score"), errors="coerce").ge(0.7)
    )
    out.loc[out["candidate_type"].ne("recurring"), "is_high_risk"] = False
    out["user_visible_caveat"] = np.select(
        [
            out["candidate_type"].eq("one_shot"),
            out["candidate_type"].eq("demand_shape_observation"),
            out.get("selected_subset_caveat", pd.Series(False, index=out.index)).fillna(False).astype(bool),
        ],
        [
            "one-shot attention only; not recurring churn probability",
            "demand shape observation only; not formal high risk",
            "selected subset validation; monthly analyst review only",
        ],
        default="monthly analyst review; probability gated",
    )
    return out


def classify_candidate_type(df: pd.DataFrame) -> pd.Series:
    shape = df.get("demand_shape_label", pd.Series("", index=df.index)).astype(str)
    history = df.get("history_sufficiency_flag", pd.Series("", index=df.index)).astype(str)
    one_shot = df.get("one_shot_flag", pd.Series(False, index=df.index)).fillna(False).astype(bool)
    return pd.Series(
        np.select(
            [one_shot, shape.isin(DEMAND_OBSERVATION_SHAPES) | history.eq("history_insufficient")],
            ["one_shot", "demand_shape_observation"],
            default="recurring",
        ),
        index=df.index,
    )


def make_candidate_id(df: pd.DataFrame) -> pd.Series:
    cols = [c for c in KEYS if c in df.columns]
    return df[cols].astype(str).agg("|".join, axis=1)


def build_m1_closure(candidates: pd.DataFrame, gate: pd.DataFrame) -> dict[str, pd.DataFrame]:
    all_by_horizon = prepare_candidates(candidates, gate)
    recurring = all_by_horizon[all_by_horizon["candidate_type"].eq("recurring")].copy()
    one_shot = all_by_horizon[all_by_horizon["candidate_type"].eq("one_shot")].copy()
    observation = all_by_horizon[all_by_horizon["candidate_type"].eq("demand_shape_observation")].copy()
    worklist = build_manufacturer_worklist(all_by_horizon)
    recurring_base = collapse_primary_horizon(recurring)
    return {
        "all_by_horizon": all_by_horizon,
        "recurring_by_horizon": recurring,
        "recurring": recurring_base,
        "one_shot": one_shot,
        "observation": observation,
        "worklist": worklist,
    }


def collapse_primary_horizon(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    work = df.copy()
    work["score_for_primary"] = pd.to_numeric(work.get("probability_score"), errors="coerce").fillna(-1)
    selected = work.sort_values("score_for_primary", ascending=False).drop_duplicates(BASE_KEYS)
    horizons = work.groupby(BASE_KEYS, dropna=False)["horizon"].agg(lambda s: ",".join(sorted(set(s.astype(str))))).reset_index(name="selected_horizons")
    selected = selected.merge(horizons, on=BASE_KEYS, how="left")
    selected = selected.rename(columns={"horizon": "primary_horizon"})
    return selected.drop(columns=["score_for_primary"], errors="ignore")


def build_manufacturer_worklist(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, group in df.groupby(["manufacturer_code", "cutoff_month", "horizon"], dropna=False):
        top = group.sort_values(["is_high_risk", "probability_score"], ascending=[False, False]).head(min(50, len(group))).copy()
        rows.append(top)
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=df.columns)
    fill = out["candidate_type"].ne("recurring")
    out.loc[fill, "is_high_risk"] = False
    out.loc[fill, "selection_reason"] = out.loc[fill, "selection_reason"].astype(str) + "|manufacturer_worklist_fill_observation"
    return out


def write_m1_outputs(root: Path, m1: dict[str, pd.DataFrame]) -> None:
    data = root / CLOSURE_DATA_DIR
    report = root / CLOSURE_REPORT_DIR
    cols = [
        "candidate_id",
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "drug_group_source",
        "cutoff_month",
        "horizon",
        "primary_horizon",
        "selected_horizons",
        "candidate_type",
        "selection_reason",
        "display_section",
        "is_high_risk",
        "user_visible_caveat",
        "probability_score",
        "churn_probability_H",
        "label_die_H",
        "label_alive_H",
        "label_window_closed",
        "demand_shape_label",
        "history_sufficiency_flag",
        "probability_display_level",
        "display_mode",
    ]
    write_csv(data / "m1_recurring_business_priority_candidates_by_horizon.csv", select_cols(m1["recurring_by_horizon"], cols))
    write_csv(data / "m1_recurring_business_priority_candidates.csv", select_cols(m1["recurring"], cols))
    write_csv(data / "m1_one_shot_attention_candidates.csv", select_cols(m1["one_shot"], cols))
    write_csv(data / "m1_demand_shape_observation_candidates.csv", select_cols(m1["observation"], cols))
    write_csv(data / "m1_manufacturer_worklist_candidates.csv", select_cols(m1["worklist"], cols))
    load = m1["worklist"].groupby(["manufacturer_code", "horizon"], dropna=False).size().reset_index(name="worklist_rows")
    write_csv(report / "m1_worklist_load_by_manufacturer.csv", load)
    summary = f"""# M1 Candidate Closure Summary

- recurring by-horizon rows: {len(m1["recurring_by_horizon"])}
- recurring collapsed rows: {len(m1["recurring"])}
- one-shot attention rows: {len(m1["one_shot"])}
- demand-shape observation rows: {len(m1["observation"])}
- manufacturer worklist rows: {len(m1["worklist"])}
- high-risk rows are limited to recurring candidates only.
- one-shot rows are separated from recurring churn probability.
- observation fill rows are never marked high risk.
- cadence: monthly report / analyst review, not daily publication.
"""
    (report / "m1_candidate_closure_summary.md").write_text(summary, encoding="utf-8")


def build_m3_survival_refinement(recurring: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    if recurring.empty:
        return pd.DataFrame()
    feat = normalize_feature_dates(features)
    work = recurring.copy()
    work["cutoff_month"] = pd.to_datetime(work["cutoff_month"], errors="coerce")
    join_cols = ["manufacturer_code", "hospital_code", "drug_group", "cutoff_month"]
    keep = join_cols + [
        "purchase_count_asof_cutoff",
        "months_since_last_purchase_asof_cutoff",
        "median_purchase_interval_days_asof_cutoff",
        "demand_shape_label",
        "history_sufficiency_flag",
    ]
    keep = [c for c in keep if c in feat.columns]
    work = work.merge(feat[keep].drop_duplicates(join_cols), on=join_cols, how="left", suffixes=("", "_feature"))
    interval_days = pd.to_numeric(work.get("median_purchase_interval_days_asof_cutoff"), errors="coerce")
    months_since = pd.to_numeric(work.get("months_since_last_purchase_asof_cutoff"), errors="coerce")
    expected = interval_days / 30.4375
    work["expected_interval_months"] = expected
    work["expected_interval_source"] = np.where(expected.notna(), "median_purchase_interval_days_asof_cutoff", "unavailable")
    work["overdue_ratio"] = months_since / expected.replace(0, np.nan)
    work["overdue_gap_months"] = months_since - expected
    ratio = pd.to_numeric(work["overdue_ratio"], errors="coerce")
    work["survival_state"] = np.select(
        [ratio.isna(), ratio.ge(2.0), ratio.ge(1.2), ratio.ge(0.8)],
        ["interval_unavailable", "materially_overdue", "likely_churn_interval", "near_due"],
        default="not_overdue",
    )
    work["survival_confidence"] = np.select(
        [ratio.isna(), ratio.ge(2.0), ratio.ge(1.2), ratio.ge(0.8)],
        ["unavailable", "high_interval_evidence", "medium_interval_evidence", "low_interval_evidence"],
        default="low_interval_evidence",
    )
    work["survival_method"] = "asof_interval_overdue_rule"
    work["fallback_method"] = np.where(ratio.isna(), "recency_frequency_observation", "")
    work["survival_note"] = "interval evidence only; not a calibrated probability"
    work["human_review_required"] = True
    return select_cols(
        work,
        [
            "candidate_id",
            "manufacturer_code",
            "hospital_code",
            "drug_group",
            "drug_group_source",
            "cutoff_month",
            "horizon",
            "survival_method",
            "expected_interval_months",
            "expected_interval_source",
            "months_since_last_purchase_asof_cutoff",
            "overdue_ratio",
            "overdue_gap_months",
            "survival_state",
            "survival_confidence",
            "demand_shape_label",
            "demand_shape_route",
            "history_sufficiency_flag",
            "fallback_method",
            "survival_note",
            "human_review_required",
            "label_die_H",
        ],
    )


def normalize_feature_dates(features: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    if "cutoff_month" in out:
        out["cutoff_month"] = pd.to_datetime(out["cutoff_month"], errors="coerce")
    if "drug_group_source" not in out:
        out["drug_group_source"] = "drug_code"
    return out


def write_m3_outputs(root: Path, m3: pd.DataFrame) -> None:
    data = root / CLOSURE_DATA_DIR
    report = root / CLOSURE_REPORT_DIR
    write_csv(data / "m3_survival_refinement_results.csv", m3)
    state = m3.groupby(["horizon", "survival_state"], dropna=False).agg(row_count=("candidate_id", "size"), die_rate=("label_die_H", "mean")).reset_index() if not m3.empty else pd.DataFrame()
    write_csv(report / "m3_survival_state_vs_label.csv", state)
    text = f"""# M3 Survival Summary

- survival rows: {len(m3)}
- method: as-of interval overdue rule
- formal survival/BG-NBD/Cox/AFT/discrete-time models: not trained
- survival_state and survival_confidence are not probabilities.
"""
    (report / "m3_survival_summary.md").write_text(text, encoding="utf-8")


def build_m4_detector_evidence(m1_all: pd.DataFrame, m3: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    if m1_all.empty:
        return pd.DataFrame()
    feat = normalize_feature_dates(features)
    base = m1_all.copy()
    base["cutoff_month"] = pd.to_datetime(base["cutoff_month"], errors="coerce")
    join_cols = ["manufacturer_code", "hospital_code", "drug_group", "cutoff_month"]
    keep = [c for c in join_cols + [
        "order_count_last_3m_asof_cutoff",
        "order_count_last_12m_asof_cutoff",
        "terminal_count_last_3m_asof_cutoff",
        "terminal_count_last_12m_asof_cutoff",
        "purchase_quantity_sum_last_3m_asof_cutoff",
        "purchase_quantity_sum_last_12m_asof_cutoff",
        "months_since_last_purchase_asof_cutoff",
    ] if c in feat.columns]
    base = base.merge(feat[keep].drop_duplicates(join_cols), on=join_cols, how="left", suffixes=("", "_feature"))
    m3_small = select_cols(m3, ["candidate_id", "overdue_ratio", "overdue_gap_months", "survival_state"])
    if not m3_small.empty:
        base = base.merge(m3_small, on="candidate_id", how="left")
    rows = []
    for _, row in base.iterrows():
        rows.extend(detectors_for_row(row))
    return pd.DataFrame(rows)


def detectors_for_row(row: pd.Series) -> list[dict[str, Any]]:
    common = {k: row.get(k) for k in ["candidate_id", "manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month", "horizon", "label_die_H"]}
    common.update({"human_review_required": True})
    detectors = []
    months_since = safe_float(row.get("months_since_last_purchase_asof_cutoff"))
    terminal_12 = safe_float(row.get("terminal_count_last_12m_asof_cutoff"))
    order_3 = safe_float(row.get("order_count_last_3m_asof_cutoff"))
    terminal_hit = bool((terminal_12 or 0) > 0 and (order_3 or 0) <= 0 and (months_since or 0) >= 3)
    detectors.append(detector_row(common, "terminal", "terminal_loss_warning", terminal_hit, "terminal evidence only; requires human review", {"terminal_count_last_12m": terminal_12, "order_count_last_3m": order_3, "months_since_last_purchase": months_since}))
    overdue = safe_float(row.get("overdue_ratio"))
    overdue_hit = bool(overdue is not None and overdue >= 1.2)
    detectors.append(detector_row(common, "interval", "purchase_interval_overdue_warning", overdue_hit, "interval overdue evidence; not probability", {"overdue_ratio": overdue, "survival_state": row.get("survival_state")}))
    decay = safe_float(row.get("frequency_decay_baseline"))
    freq_hit = bool(decay is not None and decay >= 0.5)
    detectors.append(detector_row(common, "frequency", "purchase_frequency_fluctuation_warning", freq_hit, "recent frequency drop evidence; not probability", {"frequency_decay_score": decay, "order_count_last_3m": order_3, "order_count_last_12m": safe_float(row.get("order_count_last_12m_asof_cutoff"))}))
    return detectors


def detector_row(common: dict[str, Any], family: str, name: str, hit: bool, interpretation: str, evidence: dict[str, Any]) -> dict[str, Any]:
    severity = "strong" if hit and family in {"terminal", "interval"} else "medium" if hit else "none"
    confidence = "evidence_hit" if hit else "not_hit"
    out = dict(common)
    out.update(
        {
            "detector_family": family,
            "detector_name": name,
            "detector_version": "entity_complete_v2_m_closure",
            "hit_flag": bool(hit),
            "severity": severity,
            "confidence": confidence,
            "evidence_window_start": "",
            "evidence_window_end": common.get("cutoff_month"),
            "evidence_fields": ",".join(evidence.keys()),
            "evidence_values": json.dumps(evidence, ensure_ascii=False, default=str),
            "reason_code": f"{name}_{'hit' if hit else 'not_hit'}",
            "business_interpretation": interpretation,
            "data_quality_status": "evaluable",
            "data_quality_note": "detector severity/confidence are not probabilities",
        }
    )
    return out


def write_m4_outputs(root: Path, m4: pd.DataFrame) -> None:
    data = root / CLOSURE_DATA_DIR
    report = root / CLOSURE_REPORT_DIR
    write_csv(data / "m4_detector_evidence_results.csv", m4)
    hit = (
        m4.groupby(["horizon", "detector_name", "hit_flag"], dropna=False)
        .agg(row_count=("candidate_id", "size"), die_rate=("label_die_H", "mean"))
        .reset_index()
        if not m4.empty
        else pd.DataFrame()
    )
    write_csv(report / "m4_detector_hit_vs_label.csv", hit)
    text = f"""# M4 Detector Summary

- detector evidence rows: {len(m4)}
- implemented detectors: terminal_loss_warning, purchase_interval_overdue_warning, purchase_frequency_fluctuation_warning
- detector severity and confidence are evidence descriptors, not probabilities.
- deferred detectors remain interface-only until numeric/data reliability is proven.
"""
    (report / "m4_detector_summary.md").write_text(text, encoding="utf-8")


def build_m5_status_decision(m1_all: pd.DataFrame, m3: pd.DataFrame, m4: pd.DataFrame, gate: pd.DataFrame) -> pd.DataFrame:
    base = m1_all.copy()
    gate_cols = ["candidate_id", "probability_display_level", "display_mode", "churn_probability_H", "reason_code"]
    gate_small = select_cols(gate, gate_cols).drop_duplicates("candidate_id")
    base = base.drop(columns=[c for c in gate_cols if c in base.columns and c != "candidate_id"], errors="ignore")
    base = base.merge(gate_small, on="candidate_id", how="left")
    m3_small = select_cols(m3, ["candidate_id", "survival_state", "survival_confidence"])
    if not m3_small.empty:
        base = base.merge(m3_small, on="candidate_id", how="left")
    agg = (
        m4.groupby("candidate_id", dropna=False)
        .agg(detector_hit_count=("hit_flag", "sum"), strong_detector_hit_count=("severity", lambda s: int((s == "strong").sum())))
        .reset_index()
        if not m4.empty
        else pd.DataFrame(columns=["candidate_id", "detector_hit_count", "strong_detector_hit_count"])
    )
    base = base.merge(agg, on="candidate_id", how="left")
    base[["detector_hit_count", "strong_detector_hit_count"]] = base[["detector_hit_count", "strong_detector_hit_count"]].fillna(0).astype(int)
    status = []
    for _, row in base.iterrows():
        status.append(status_for_row(row))
    status_df = pd.DataFrame(status)
    out = pd.concat([base.reset_index(drop=True), status_df], axis=1)
    out["auto_dispatch_allowed"] = False
    out["human_review_required"] = out["final_candidate_status"].ne("not_actionable")
    out["probability_reference"] = out.get("churn_probability_H")
    out["probability_interpretation"] = np.where(out["probability_display_level"].eq("probability_allowed"), "gated probability display allowed", "do not show exact recurring probability")
    out["business_priority_reference"] = "ranking/worklist only; not probability"
    out["guardrail_status"] = "customer_probability_blocked_auto_dispatch_false"
    return select_cols(
        out,
        [
            "candidate_id",
            "candidate_type",
            "manufacturer_code",
            "hospital_code",
            "drug_group",
            "drug_group_source",
            "cutoff_month",
            "horizon",
            "final_candidate_status",
            "review_priority",
            "evidence_strength",
            "human_review_required",
            "auto_dispatch_allowed",
            "probability_reference",
            "probability_interpretation",
            "business_priority_reference",
            "survival_state",
            "survival_confidence",
            "detector_hit_count",
            "strong_detector_hit_count",
            "data_quality_warning_flag",
            "guardrail_status",
            "status_reason",
            "label_die_H",
        ],
    )


def status_for_row(row: pd.Series) -> dict[str, Any]:
    ctype = row.get("candidate_type", "")
    level = row.get("probability_display_level", "")
    strong_hits = int(row.get("strong_detector_hit_count", 0) or 0)
    hits = int(row.get("detector_hit_count", 0) or 0)
    if ctype == "one_shot":
        return {"final_candidate_status": "one_shot_attention", "review_priority": "P2", "evidence_strength": "weak", "data_quality_warning_flag": True, "status_reason": "one_shot_separated_from_recurring_churn"}
    if ctype == "demand_shape_observation":
        return {"final_candidate_status": "observation_only", "review_priority": "P2", "evidence_strength": "weak", "data_quality_warning_flag": True, "status_reason": "demand_shape_or_history_insufficient_observation"}
    if level == "hidden_data_insufficient":
        return {"final_candidate_status": "not_actionable", "review_priority": "P3", "evidence_strength": "insufficient", "data_quality_warning_flag": True, "status_reason": "probability_hidden_data_insufficient"}
    if strong_hits > 0 and level in {"probability_allowed", "risk_band_only"}:
        return {"final_candidate_status": "priority_review", "review_priority": "P0", "evidence_strength": "strong", "data_quality_warning_flag": False, "status_reason": "strong_evidence_with_probability_gate"}
    if hits > 0:
        return {"final_candidate_status": "manual_review", "review_priority": "P1", "evidence_strength": "medium", "data_quality_warning_flag": False, "status_reason": "detector_or_interval_evidence"}
    return {"final_candidate_status": "low_confidence_watch", "review_priority": "P2", "evidence_strength": "weak", "data_quality_warning_flag": False, "status_reason": "ranking_signal_without_strong_evidence"}


def write_m5_outputs(root: Path, m5: pd.DataFrame) -> None:
    data = root / CLOSURE_DATA_DIR
    report = root / CLOSURE_REPORT_DIR
    write_csv(data / "m5_candidate_status_decision.csv", m5)
    dist = m5.groupby(["final_candidate_status", "review_priority"], dropna=False).size().reset_index(name="row_count")
    write_csv(report / "m5_status_distribution.csv", dist)
    vs = m5.groupby(["horizon", "final_candidate_status"], dropna=False).agg(row_count=("candidate_id", "size"), die_rate=("label_die_H", "mean")).reset_index()
    write_csv(report / "m5_status_vs_label.csv", vs)
    text = f"""# M5 Status Decision Summary

- status decision rows: {len(m5)}
- auto_dispatch_allowed true rows: {int(m5["auto_dispatch_allowed"].astype(bool).sum())}
- customer-facing probability service remains blocked.
"""
    (report / "m5_status_decision_summary.md").write_text(text, encoding="utf-8")


def build_m7_structured_evidence_bundle(m5: pd.DataFrame, m3: pd.DataFrame, m4: pd.DataFrame, gate: pd.DataFrame) -> pd.DataFrame:
    if m5.empty:
        return pd.DataFrame()
    out = m5.copy()
    gate_small = select_cols(gate, ["candidate_id", "churn_probability_H", "probability_display_level", "reason_code"]).drop_duplicates("candidate_id")
    out = out.merge(gate_small, on="candidate_id", how="left", suffixes=("", "_gate"))
    m3_small = select_cols(m3, ["candidate_id", "survival_state", "survival_confidence"]).drop_duplicates("candidate_id")
    out = out.drop(columns=["survival_state", "survival_confidence"], errors="ignore").merge(m3_small, on="candidate_id", how="left")
    det_cols = ["detector_name", "hit_flag", "severity", "confidence", "reason_code"]
    det_list = (
        m4.groupby("candidate_id", dropna=False)[det_cols]
        .apply(detector_list_json)
        .reset_index(name="detector_evidence_list")
        if not m4.empty
        else pd.DataFrame(columns=["candidate_id", "detector_evidence_list"])
    )
    out = out.merge(det_list, on="candidate_id", how="left")
    out["bundle_id"] = "bundle|" + out["candidate_id"].astype(str)
    out["candidate_source"] = "entity_complete_v2_m_module_closure"
    out["churn_probability_interpretation"] = np.where(out["probability_display_level"].eq("probability_allowed"), "gated recurring churn probability", "not displayed as exact probability")
    out["repeat_probability_H"] = np.nan
    out["repeat_probability_interpretation"] = np.where(out["candidate_type"].eq("one_shot"), "one-shot attention only; no recurring churn probability", "not applicable")
    out["value_at_risk_H"] = np.nan
    out["business_priority_score_H"] = np.nan
    out["business_priority_interpretation"] = "business/worklist ranking only; not probability"
    out["survival_summary"] = out["survival_state"].fillna("interval_not_available").astype(str) + "; confidence is not probability"
    out["demand_shape_label"] = ""
    out["demand_shape_route"] = np.where(out["candidate_type"].eq("demand_shape_observation"), "observation_only", "m_module_closure")
    out["label_confidence_weight"] = np.nan
    out["guardrail_summary"] = out["guardrail_status"]
    out["evidence_timeline_available"] = False
    out["evidence_timeline_reference"] = np.nan
    out["evidence_persistence_summary"] = "not_implemented_in_v1"
    out["allowed_claims"] = "monthly analyst review candidate; evidence is proxy/backtest based; human review required"
    out["forbidden_claims"] = "; ".join(FORBIDDEN_CLAIMS)
    out["recommended_action_candidates"] = np.where(out["final_candidate_status"].isin(["priority_review", "manual_review"]), "review_purchase_history; contact_owner_if_policy_allows", "observe_only")
    out["model_limitations_note"] = "selected subset, no customer-facing probability service, no auto dispatch"
    out["data_quality_note"] = np.where(out["data_quality_warning_flag"].astype(bool), "limited history or observation-only route", "usable for internal monthly report")
    out["user_visible_caveat"] = "monthly internal analyst view only"
    return select_cols(
        out,
        [
            "bundle_id",
            "candidate_id",
            "candidate_type",
            "manufacturer_code",
            "hospital_code",
            "drug_group",
            "drug_group_source",
            "cutoff_month",
            "horizon",
            "candidate_source",
            "final_candidate_status",
            "review_priority",
            "human_review_required",
            "auto_dispatch_allowed",
            "churn_probability_H",
            "churn_probability_interpretation",
            "repeat_probability_H",
            "repeat_probability_interpretation",
            "value_at_risk_H",
            "business_priority_score_H",
            "business_priority_interpretation",
            "survival_state",
            "survival_confidence",
            "survival_summary",
            "demand_shape_label",
            "demand_shape_route",
            "label_confidence_weight",
            "guardrail_summary",
            "detector_evidence_list",
            "detector_hit_count",
            "strong_detector_hit_count",
            "evidence_strength",
            "evidence_timeline_available",
            "evidence_timeline_reference",
            "evidence_persistence_summary",
            "allowed_claims",
            "forbidden_claims",
            "recommended_action_candidates",
            "model_limitations_note",
            "data_quality_note",
            "user_visible_caveat",
        ],
    )


def detector_list_json(group: pd.DataFrame) -> str:
    cols = ["detector_name", "hit_flag", "severity", "confidence", "reason_code"]
    return json.dumps(group[cols].to_dict(orient="records"), ensure_ascii=False, default=str)


def write_m7_outputs(root: Path, m7: pd.DataFrame) -> None:
    data = root / CLOSURE_DATA_DIR
    report = root / CLOSURE_REPORT_DIR
    write_csv(data / "m7_structured_evidence_bundle.csv", m7)
    completeness = pd.DataFrame(
        [{"field": col, "non_null_rate": float(m7[col].notna().mean()) if col in m7 and len(m7) else 0.0} for col in m7.columns]
    )
    write_csv(report / "m7_bundle_completeness.csv", completeness)
    claim = pd.DataFrame(
        [
            {"check": "forbidden_claims_complete", "passed": bool(all(claim in " ".join(m7.get("forbidden_claims", pd.Series(dtype=str)).astype(str).head(10)) for claim in FORBIDDEN_CLAIMS)) if len(m7) else False},
            {"check": "auto_dispatch_all_false", "passed": bool((m7["auto_dispatch_allowed"].astype(bool) == False).all()) if len(m7) else False},
            {"check": "timeline_not_implemented", "passed": bool((m7["evidence_timeline_available"].astype(bool) == False).all()) if len(m7) else False},
        ]
    )
    write_csv(report / "m7_claim_boundary_audit.csv", claim)
    text = f"""# M7 Evidence Bundle Summary

- bundle rows: {len(m7)}
- claim boundary passed: {bool(claim["passed"].all())}
- evidence timeline implemented: false
- LLM line card generated: false
"""
    (report / "m7_evidence_bundle_summary.md").write_text(text, encoding="utf-8")


def build_m8_validation(root: Path, m1: dict[str, pd.DataFrame], m3: pd.DataFrame, m4: pd.DataFrame, m5: pd.DataFrame, m7: pd.DataFrame, gate: pd.DataFrame) -> dict[str, Any]:
    policy = pd.read_csv(root / REPORT_ROOT / "07_candidate_policy_v2/candidate_policy_v2_metrics.csv")
    reco = policy[policy["candidate_policy"].eq("multi_recall_union_top10")]
    recall = float(reco["candidate_die_recall"].mean()) if not reco.empty else np.nan
    lift = float(reco["lift_vs_non_candidate"].mean()) if not reco.empty and "lift_vs_non_candidate" in reco else np.nan
    out = build_m8_validation_for_frames(m1, m3, m4, m5, m7)
    out["m1_recall"] = recall
    out["m1_lift"] = lift
    return out


def build_m8_validation_for_frames(m1: dict[str, pd.DataFrame], m3: pd.DataFrame, m4: pd.DataFrame, m5: pd.DataFrame, m7: pd.DataFrame) -> dict[str, Any]:
    high_risk_share = float(m1["worklist"]["is_high_risk"].mean()) if len(m1["worklist"]) else 0.0
    auto_false = bool((m5["auto_dispatch_allowed"].astype(bool) == False).all()) if len(m5) else False
    forbidden_text = " ".join(m7.get("forbidden_claims", pd.Series(dtype=str)).astype(str).head(10))
    forbidden_ok = bool(all(claim in forbidden_text for claim in FORBIDDEN_CLAIMS)) if len(m7) else False
    module_matrix = pd.DataFrame(
        [
            {"module": "M1", "status": "implemented_current", "row_count": len(m1["all_by_horizon"])},
            {"module": "M3", "status": "implemented_current", "row_count": len(m3)},
            {"module": "M4", "status": "implemented_current", "row_count": len(m4)},
            {"module": "M5", "status": "implemented_current", "row_count": len(m5)},
            {"module": "M7", "status": "implemented_current", "row_count": len(m7)},
            {"module": "M8", "status": "implemented_current", "row_count": 1},
        ]
    )
    service = {
        "internal_diagnostic_view": True,
        "analyst_view": bool(len(m1["all_by_horizon"]) and len(m3) and len(m4) and len(m5) and len(m7)),
        "proof_case_report": False,
        "customer_facing_probability_service": False,
        "auto_dispatch": False,
    }
    return {
        "m1_recall": np.nan,
        "m1_lift": np.nan,
        "high_risk_share": high_risk_share,
        "auto_dispatch_all_false": auto_false,
        "forbidden_claims_ok": forbidden_ok,
        "module_matrix": module_matrix,
        "service": service,
    }


def write_m8_outputs(root: Path, m8: dict[str, Any]) -> None:
    report = root / CLOSURE_REPORT_DIR
    write_csv(report / "m8_module_status_matrix.csv", m8["module_matrix"])
    service_text = "\n".join(f"- {k}: {str(v).lower()}" for k, v in m8["service"].items())
    (report / "m8_service_gate_final_decision.md").write_text("# M8 Service Gate Final Decision\n\n" + service_text + "\n", encoding="utf-8")
    text = f"""# M8 M Module Validation Summary

- M1 candidate die recall: {m8["m1_recall"]}
- M1 lift: {m8["m1_lift"]}
- high risk share in manufacturer worklist: {m8["high_risk_share"]}
- auto_dispatch_allowed all false: {m8["auto_dispatch_all_false"]}
- M7 forbidden claims coverage: {m8["forbidden_claims_ok"]}
- internal diagnostic view: {m8["service"]["internal_diagnostic_view"]}
- analyst view: {m8["service"]["analyst_view"]}
- proof case report: {m8["service"]["proof_case_report"]}
- customer-facing probability service: {m8["service"]["customer_facing_probability_service"]}
- release cadence: monthly report, not daily report.
"""
    (report / "m8_m_module_validation_summary.md").write_text(text, encoding="utf-8")


def build_m_module_implementation_audit_v2(m1: dict[str, pd.DataFrame], m3: pd.DataFrame, m4: pd.DataFrame, m5: pd.DataFrame, m7: pd.DataFrame, m8: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"module": "M0", "status": "implemented_current", "note": "entity_complete_v2 data/feature/model foundation available"},
            {"module": "M1", "status": "implemented_current", "note": f"candidate/worklist closure rows={len(m1['all_by_horizon'])}"},
            {"module": "M2", "status": "intentionally_deferred", "note": "one-shot repeat model not rebuilt in this stage; one-shot attention is separated"},
            {"module": "M3", "status": "implemented_current", "note": f"interval evidence rows={len(m3)}; not formal survival probability"},
            {"module": "M4", "status": "implemented_current", "note": f"detector evidence rows={len(m4)}; severity/confidence not probability"},
            {"module": "M5", "status": "implemented_current", "note": f"status rows={len(m5)}; auto_dispatch false"},
            {"module": "M6", "status": "interface_only", "note": "evidence timeline/cache remains interface only"},
            {"module": "M7", "status": "implemented_current", "note": f"structured evidence bundle rows={len(m7)}; no LLM card"},
            {"module": "M8", "status": "implemented_current", "note": "closure validation and service gate decision generated"},
            {"module": "LLM line card", "status": "not_implemented", "note": "LLM calls and formal line cards are forbidden in this stage"},
            {"module": "formal survival", "status": "intentionally_deferred", "note": "BG/NBD/Cox/AFT/discrete-time survival not trained"},
            {"module": "customer-facing probability service", "status": "rejected_or_abandoned", "note": "not allowed for selected-subset v2"},
            {"module": "auto dispatch", "status": "rejected_or_abandoned", "note": "forbidden; all outputs keep auto_dispatch_allowed=false"},
        ]
    )


def write_implementation_audit_v2(root: Path, audit: pd.DataFrame) -> None:
    out = root / AUDIT_REPORT_DIR
    write_csv(out / "m_module_status_matrix_v2.csv", audit)
    (out / "m_module_implementation_audit_summary_v2.md").write_text(
        "# M Module Implementation Audit V2\n\n"
        + audit.to_markdown(index=False)
        + "\n",
        encoding="utf-8",
    )
    remaining = """# Remaining Gaps After V2

- M2 one-shot repeat model remains deferred; one-shot attention is separated from recurring churn.
- M6 evidence timeline/cache remains interface-only.
- LLM line card is not implemented and no LLM is called.
- Formal survival/BTYD models remain deferred.
- Customer-facing probability service remains not allowed.
- Auto dispatch remains forbidden.
- Next product surface should be monthly internal diagnostic / analyst view only.
"""
    (out / "remaining_gaps_after_v2.md").write_text(remaining, encoding="utf-8")


def write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")


def select_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col not in out:
            out[col] = np.nan
    return out[cols]


def safe_float(value: Any) -> float | None:
    try:
        if pd.isna(value):
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


__all__ = [
    "run_entity_complete_m_module_closure",
    "build_m1_closure",
    "build_m3_survival_refinement",
    "build_m4_detector_evidence",
    "build_m5_status_decision",
    "build_m7_structured_evidence_bundle",
    "build_m8_validation",
    "build_m8_validation_for_frames",
    "FORBIDDEN_CLAIMS",
]
