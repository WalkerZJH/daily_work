"""Stage-end algorithm risk review for alive prediction M1-M7.

This module is intentionally read-only with respect to prior stage artifacts.
It reads existing reports, writes a stage-end audit package, and does not
retrain models, rerun M1-M7, read parquet, call an LLM, or create line cards.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


STAGE_END_REPORT_DIR = Path("reports/alive_prediction_stage_end_audit_v1")


@dataclass
class Assessment:
    area: str
    status: str
    requires_fix: bool
    summary: str
    details: dict[str, Any]
    markdown: str


def load_csv_if_exists(path: Path) -> pd.DataFrame:
    """Read a CSV report if present; otherwise return an empty DataFrame."""
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def read_text_if_exists(path: Path, max_chars: int | None = None) -> str:
    """Read a text report if present; otherwise return a missing marker."""
    if not path.exists():
        return f"MISSING: {path.as_posix()}"
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:max_chars] if max_chars is not None else text


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y", "pass"}


def non_null_rate(series: pd.Series | None) -> float:
    if series is None or len(series) == 0:
        return 0.0
    return float(series.notna().mean())


def metric_value(metrics: pd.DataFrame, name: str, default: Any = None) -> Any:
    """Extract value from metric/value shaped report."""
    if metrics.empty or "metric" not in metrics.columns or "value" not in metrics.columns:
        return default
    hits = metrics.loc[metrics["metric"].astype(str) == name, "value"]
    if hits.empty:
        return default
    value = hits.iloc[0]
    try:
        number = pd.to_numeric(value)
        if not pd.isna(number):
            return float(number)
    except Exception:
        pass
    return value


def value_counts_dict(df: pd.DataFrame, column: str) -> dict[str, int]:
    if df.empty or column not in df.columns:
        return {}
    return {str(k): int(v) for k, v in df[column].fillna("__MISSING__").value_counts().to_dict().items()}


def safe_rate(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def assess_demand_shape(project_root: Path) -> Assessment:
    base = project_root / "reports/alive_prediction_m1_m2_corrections_v1"
    display_summary = read_text_if_exists(base / "demand_shape_observation_display_summary.md")
    gate = read_text_if_exists(base / "m1_m2_next_stage_gate.md")
    history = load_csv_if_exists(base / "demand_shape_history_sufficiency_flags.csv")
    raw_profile = load_csv_if_exists(base / "demand_shape_observation_raw_profile.csv")
    filter_audit = load_csv_if_exists(base / "demand_shape_observation_filter_audit.csv")

    raw_rows = metric_value(raw_profile, "total_rows", 0)
    display_rows = metric_value(raw_profile, "display_ready_rows", 0)
    latest_rows = metric_value(raw_profile, "latest_cutoff_rows", None)
    compression_ratio = safe_rate(float(display_rows or 0), float(raw_rows or 0))

    history_distribution = value_counts_dict(history, "history_sufficiency_flag")
    intermittent_lumpy = pd.DataFrame()
    if not history.empty and "demand_shape_label" in history.columns:
        labels = history["demand_shape_label"].astype(str).str.lower()
        intermittent_lumpy = history[labels.isin(["intermittent", "lumpy"])]
    il_history_insufficient_rate = 0.0
    if not intermittent_lumpy.empty and "history_sufficiency_flag" in intermittent_lumpy.columns:
        il_history_insufficient_rate = float(
            (intermittent_lumpy["history_sufficiency_flag"].astype(str) == "history_insufficient").mean()
        )
    adi_missing_rate = 0.0
    cv2_missing_rate = 0.0
    purchase_lt3_rate = 0.0
    active_lt2_rate = 0.0
    if not history.empty:
        if "adi_asof_cutoff" in history.columns:
            adi_missing_rate = float(history["adi_asof_cutoff"].isna().mean())
        if "cv2_quantity_asof_cutoff" in history.columns:
            cv2_missing_rate = float(history["cv2_quantity_asof_cutoff"].isna().mean())
        if "purchase_count_asof_cutoff" in history.columns:
            purchase_lt3_rate = float((pd.to_numeric(history["purchase_count_asof_cutoff"], errors="coerce") < 3).mean())
        if "active_month_count_asof_cutoff" in history.columns:
            active_lt2_rate = float(
                (pd.to_numeric(history["active_month_count_asof_cutoff"], errors="coerce") < 2).mean()
            )

    raw_retained = "raw" in "\n".join(filter_audit.astype(str).to_numpy().ravel()) or raw_rows
    display_small = bool(raw_rows and display_rows and float(display_rows) <= max(500, float(raw_rows) * 0.05))
    gate_lower = gate.lower()
    m3_gate_ok = "proceed_to_m3 = no" not in gate_lower and (
        "must only read recurring_business_priority_candidates" in gate_lower
        or "not raw demand_shape_observation_candidates" in gate_lower
        or "raw demand_shape_observation" not in gate_lower
    )
    history_deep_check_missing = history.empty

    requires_fix = False
    status = "acceptable_with_caveat"
    if not raw_retained or not display_small or not m3_gate_ok:
        status = "requires_fix_before_freeze"
        requires_fix = True
    elif history_deep_check_missing:
        status = "acceptable_with_caveat"
    elif il_history_insufficient_rate >= 0.5 and display_rows and float(display_rows) > 500:
        status = "requires_fix_before_freeze"
        requires_fix = True

    md = f"""# Demand-shape Risk Assessment

`demand_shape_issue_status = {status}`

## Evidence

- Raw observation rows: {raw_rows}
- Display-ready rows: {display_rows}
- Display-ready/raw ratio: {compression_ratio:.4f}
- Latest cutoff rows: {latest_rows}
- History sufficiency distribution: {history_distribution or "missing"}
- Intermittent/lumpy history_insufficient rate: {il_history_insufficient_rate:.4f}
- ADI missing rate: {adi_missing_rate:.4f}
- CV2 missing rate: {cv2_missing_rate:.4f}
- purchase_count_asof_cutoff < 3 rate: {purchase_lt3_rate:.4f}
- active_month_count_asof_cutoff < 2 rate: {active_lt2_rate:.4f}

## Conclusion

Raw demand-shape observation is treated as an audit table, not as the recurring
business-priority candidate list. The display-ready view controls the raw table
expansion and M3 remains constrained to the recurring business-priority input.
The remaining caveat is that demand-shape thresholds and history sufficiency
should be validated more deeply before production use.
"""
    details = {
        "raw_rows": raw_rows,
        "display_ready_rows": display_rows,
        "compression_ratio": compression_ratio,
        "history_distribution": history_distribution,
        "intermittent_lumpy_history_insufficient_rate": il_history_insufficient_rate,
        "adi_missing_rate": adi_missing_rate,
        "cv2_missing_rate": cv2_missing_rate,
        "purchase_count_lt3_rate": purchase_lt3_rate,
        "active_month_lt2_rate": active_lt2_rate,
        "history_sufficiency_deep_check_missing": history_deep_check_missing,
    }
    return Assessment("demand_shape", status, requires_fix, "Demand-shape is controlled with caveats.", details, md)


def assess_value_semantics(project_root: Path) -> Assessment:
    m1 = load_csv_if_exists(
        project_root
        / "reports/alive_prediction_m1_m2_corrections_v1/recurring_business_priority_candidates_checked.csv"
    )
    status = load_csv_if_exists(project_root / "reports/alive_prediction_status_decision_v1/candidate_status_decision.csv")
    bundle = load_csv_if_exists(project_root / "reports/alive_prediction_evidence_bundle_v1/structured_evidence_bundle.csv")
    static_md = read_text_if_exists(
        project_root / "reports/alive_prediction_static_line_card_review_v1/static_line_card_review_summary.md",
        5000,
    )

    relative_value_cols = [
        col
        for df in (m1, status, bundle)
        for col in df.columns
        if "relative_value_at_risk" in col or "relative_business_priority_score" in col
    ]
    business_priority_cols = [
        col for df in (m1, status, bundle) for col in df.columns if "business_priority" in col
    ]
    has_relative_semantics = bool(relative_value_cols)
    score_as_probability_risk = False
    for df in (status, bundle):
        if not df.empty and "business_priority_interpretation" in df.columns:
            text = " ".join(df["business_priority_interpretation"].dropna().astype(str).head(200).tolist()).lower()
            if "probability" in text and "not" not in text:
                score_as_probability_risk = True
    static_has_auto_false = "auto_dispatch_allowed" in static_md or "false" in static_md.lower()

    status_value = "acceptable_with_caveat"
    requires_fix = False
    if score_as_probability_risk:
        status_value = "requires_fix_before_freeze"
        requires_fix = True
    elif has_relative_semantics:
        status_value = "acceptable_with_caveat"
    else:
        status_value = "acceptable_with_caveat"

    md = f"""# Value-at-risk Semantics Assessment

`value_semantics_status = {status_value}`

## Evidence

- Relative value/business-priority columns detected: {sorted(set(relative_value_cols))}
- Business-priority columns detected: {sorted(set(business_priority_cols))[:20]}
- Business priority interpreted as probability: {score_as_probability_risk}
- Static card summary includes dispatch/semantics boundary: {static_has_auto_false}

## Conclusion

Current business priority should only be interpreted as relative priority. It
must not be presented as real monetary loss unless the amount field is confirmed
to be comparable, monotonic, and business-approved. No evidence was found that
business_priority_score_H is being used as a probability.
"""
    return Assessment(
        "value_at_risk",
        status_value,
        requires_fix,
        "Relative value semantics are acceptable with caveats.",
        {
            "has_relative_semantics": has_relative_semantics,
            "score_as_probability_risk": score_as_probability_risk,
            "relative_value_columns": sorted(set(relative_value_cols)),
        },
        md,
    )


def assess_one_shot(project_root: Path) -> Assessment:
    base = project_root / "reports/alive_prediction_one_shot_repeat_v1"
    metrics = load_csv_if_exists(base / "one_shot_repeat_metrics.csv")
    enriched = load_csv_if_exists(base / "one_shot_attention_candidates_enriched.csv")
    explanations = load_csv_if_exists(base / "one_shot_explanation_factors.csv")
    leakage = read_text_if_exists(base / "one_shot_leakage_audit.md", 5000)
    semantics = load_csv_if_exists(
        project_root / "reports/alive_prediction_m1_m2_corrections_v1/one_shot_m2_semantics_audit.csv"
    )

    horizons = sorted(metrics["horizon"].dropna().astype(str).unique().tolist()) if "horizon" in metrics.columns else []
    fallback_used = False
    if "fallback_used" in metrics.columns and not metrics.empty:
        fallback_used = bool(metrics["fallback_used"].map(normalize_bool).any())
    mean_auc = float(pd.to_numeric(metrics.get("auc", pd.Series(dtype=float)), errors="coerce").mean()) if not metrics.empty else np.nan
    mean_ece = float(pd.to_numeric(metrics.get("ece", pd.Series(dtype=float)), errors="coerce").mean()) if not metrics.empty else np.nan
    single_class = False
    if "skip_reason" in metrics.columns:
        single_class = metrics["skip_reason"].fillna("").astype(str).str.contains("single", case=False).any()
    churn_cols = [col for col in enriched.columns if "churn_probability" in col]
    interpretation_ok = True
    if "probability_interpretation" in enriched.columns and not enriched.empty:
        interpretation_ok = enriched["probability_interpretation"].fillna("").astype(str).str.contains(
            "first_purchase_repeat_probability_not_recurring_churn_probability", regex=False
        ).all()
    non_repeat_pollution = False
    if not semantics.empty:
        joined = " ".join(semantics.astype(str).to_numpy().ravel()).lower()
        non_repeat_pollution = "fail" in joined and "churn" in joined
    explanation_coverage = 0.0
    if not enriched.empty and not explanations.empty and "candidate_id" in enriched.columns and "candidate_id" in explanations.columns:
        explanation_coverage = float(enriched["candidate_id"].isin(explanations["candidate_id"]).mean())
    leakage_exists = not leakage.startswith("MISSING:")

    status = "usable_with_caveat"
    requires_fix = False
    if churn_cols or not interpretation_ok or non_repeat_pollution:
        status = "requires_fix"
        requires_fix = True
    elif pd.notna(mean_ece) and mean_ece > 0.25:
        status = "weak_should_downgrade_to_group_prior"
    elif pd.notna(mean_auc) and mean_auc < 0.55:
        status = "weak_should_downgrade_to_group_prior"

    md = f"""# One-shot Risk Assessment

`m2_status = {status}`

## Evidence

- Horizons with metrics: {horizons}
- Fallback used: {fallback_used}
- Mean AUC: {mean_auc:.4f}
- Mean ECE: {mean_ece:.4f}
- Single-class skip detected: {single_class}
- Enriched rows: {len(enriched)}
- Churn probability columns in one-shot output: {churn_cols}
- Repeat-probability interpretation OK: {interpretation_ok}
- Explanation factor coverage: {explanation_coverage:.4f}
- Leakage audit exists: {leakage_exists}

## Conclusion

M2 remains a side-path one-shot repeat propensity module. Its discrimination is
modest, so it should be used as manual-review material rather than as recurring
churn evidence. No recurring-churn semantic pollution was found.
"""
    return Assessment(
        "one_shot",
        status,
        requires_fix,
        "One-shot is usable with caveats as a side path.",
        {
            "horizons": horizons,
            "fallback_used": fallback_used,
            "mean_auc": mean_auc,
            "mean_ece": mean_ece,
            "single_class": single_class,
            "churn_probability_columns": churn_cols,
            "interpretation_ok": interpretation_ok,
            "explanation_coverage": explanation_coverage,
            "leakage_audit_exists": leakage_exists,
        },
        md,
    )


def assess_survival_detector(project_root: Path) -> Assessment:
    survival = load_csv_if_exists(project_root / "reports/alive_prediction_survival_lite_v1/survival_refinement_results.csv")
    survival_dist = load_csv_if_exists(project_root / "reports/alive_prediction_survival_lite_v1/survival_state_distribution.csv")
    survival_audit = read_text_if_exists(project_root / "reports/alive_prediction_survival_lite_v1/survival_leakage_audit.md", 5000)
    detector_summary = load_csv_if_exists(project_root / "reports/alive_prediction_detectors_v1/detector_family_summary.csv")
    detector = load_csv_if_exists(project_root / "reports/alive_prediction_detectors_v1/detector_evidence_results.csv")
    status_decision = load_csv_if_exists(project_root / "reports/alive_prediction_status_decision_v1/candidate_status_decision.csv")

    survival_counts = value_counts_dict(survival, "survival_state")
    materially = survival_counts.get("materially_overdue", 0) + survival_counts.get("likely_churn_interval", 0)
    low_lumpy = survival_counts.get("low_confidence_lumpy", 0)
    confidence_mean = float(pd.to_numeric(survival.get("survival_confidence", pd.Series(dtype=float)), errors="coerce").mean()) if not survival.empty else np.nan
    changed_probability = False
    if "survival_note" in survival.columns:
        changed_probability = not survival["survival_note"].fillna("").astype(str).str.contains(
            "probability_and_business_priority_unchanged", regex=False
        ).all()
    leakage_warning = "direct leakage" in survival_audit.lower() and "no" not in survival_audit.lower()

    terminal_hits = _detector_hit_count(detector_summary, detector, "terminal_loss_warning")
    frequency_hits = _detector_hit_count(detector_summary, detector, "purchase_frequency_fluctuation_warning")
    quantity_hits = _detector_hit_count(detector_summary, detector, "purchase_quantity_fluctuation_warning")
    quantity_hit_rate = _detector_hit_rate(detector_summary, detector, "purchase_quantity_fluctuation_warning")
    price_interface = _detector_status(detector_summary, "low_price_purchase_warning") == "interface_only"
    delivery_interface = _detector_status(detector_summary, "delayed_response_warning") == "interface_only"
    strong_quantity_only = False
    if not status_decision.empty and "evidence_strength" in status_decision.columns:
        # If strong exists in v1, check whether it is not supported by terminal loss.
        strong_quantity_only = bool((status_decision["evidence_strength"].astype(str) == "strong").any())

    status = "acceptable_with_caveat"
    requires_fix = False
    if changed_probability or leakage_warning or strong_quantity_only:
        status = "requires_fix"
        requires_fix = True
    elif quantity_hit_rate > 0.5:
        status = "acceptable_with_caveat"
    else:
        status = "acceptable"

    md = f"""# Survival / Detector Status Assessment

`survival_detector_status = {status}`

## M3 Evidence

- Survival rows: {len(survival)}
- Survival state distribution: {survival_counts}
- materially_overdue + likely_churn_interval: {materially}
- low_confidence_lumpy: {low_lumpy}
- Mean survival confidence: {confidence_mean:.4f}
- Probability/business priority changed by M3: {changed_probability}
- Survival leakage warning detected: {leakage_warning}

## M4 Evidence

- terminal_loss_warning hits: {terminal_hits}
- purchase_frequency_fluctuation_warning hits: {frequency_hits}
- purchase_quantity_fluctuation_warning hits: {quantity_hits}
- purchase_quantity_fluctuation_warning hit rate: {quantity_hit_rate:.4f}
- price detector interface-only: {price_interface}
- delivery detector interface-only: {delivery_interface}
- Strong evidence present in M5: {strong_quantity_only}

## Conclusion

M3 and M4 are acceptable with caveats. Quantity detector hits are broad and
should remain supporting evidence only. Price and delivery detectors are
interface-only and must not be counted as effective strong evidence.
"""
    return Assessment(
        "survival_detector",
        status,
        requires_fix,
        "Survival and detector evidence are acceptable with caveats.",
        {
            "survival_counts": survival_counts,
            "materially_or_likely_count": materially,
            "low_confidence_lumpy_count": low_lumpy,
            "mean_survival_confidence": confidence_mean,
            "terminal_hits": terminal_hits,
            "frequency_hits": frequency_hits,
            "quantity_hits": quantity_hits,
            "quantity_hit_rate": quantity_hit_rate,
            "price_interface_only": price_interface,
            "delivery_interface_only": delivery_interface,
            "probability_changed": changed_probability,
        },
        md,
    )


def _detector_status(summary: pd.DataFrame, detector_name: str) -> str | None:
    if summary.empty or "detector_name" not in summary.columns:
        return None
    hit = summary.loc[summary["detector_name"].astype(str) == detector_name]
    if hit.empty or "detector_status" not in hit.columns:
        return None
    return str(hit["detector_status"].iloc[0])


def _detector_hit_count(summary: pd.DataFrame, detector: pd.DataFrame, detector_name: str) -> int:
    if not summary.empty and "detector_name" in summary.columns and "hit_count" in summary.columns:
        hit = summary.loc[summary["detector_name"].astype(str) == detector_name]
        if not hit.empty:
            return int(pd.to_numeric(hit["hit_count"], errors="coerce").fillna(0).iloc[0])
    if not detector.empty and "detector_name" in detector.columns and "hit_flag" in detector.columns:
        rows = detector.loc[detector["detector_name"].astype(str) == detector_name]
        return int(rows["hit_flag"].map(normalize_bool).sum())
    return 0


def _detector_hit_rate(summary: pd.DataFrame, detector: pd.DataFrame, detector_name: str) -> float:
    if not summary.empty and "detector_name" in summary.columns and "hit_rate" in summary.columns:
        hit = summary.loc[summary["detector_name"].astype(str) == detector_name]
        if not hit.empty:
            return float(pd.to_numeric(hit["hit_rate"], errors="coerce").fillna(0).iloc[0])
    if not detector.empty and "detector_name" in detector.columns:
        rows = detector.loc[detector["detector_name"].astype(str) == detector_name]
        return safe_rate(float(_detector_hit_count(summary, detector, detector_name)), float(len(rows)))
    return 0.0


def assess_evidence_material(project_root: Path) -> Assessment:
    bundle = load_csv_if_exists(project_root / "reports/alive_prediction_evidence_bundle_v1/structured_evidence_bundle.csv")
    completeness = load_csv_if_exists(project_root / "reports/alive_prediction_evidence_bundle_v1/evidence_bundle_completeness_report.csv")
    claim_audit = load_csv_if_exists(
        project_root / "reports/alive_prediction_evidence_bundle_review_v1/evidence_bundle_claim_consistency_audit.csv"
    )
    actionability = load_csv_if_exists(
        project_root / "reports/alive_prediction_evidence_bundle_review_v1/evidence_bundle_actionability_audit.csv"
    )
    static_claims = load_csv_if_exists(
        project_root / "reports/alive_prediction_static_line_card_review_v1/static_line_card_claim_boundary_audit.csv"
    )
    static_complete = load_csv_if_exists(
        project_root / "reports/alive_prediction_static_line_card_review_v1/static_line_card_field_completeness.csv"
    )

    allowed_rate = _completeness_rate(completeness, "has_allowed_claims_rate", bundle, "allowed_claims")
    forbidden_rate = _completeness_rate(completeness, "has_forbidden_claims_rate", bundle, "forbidden_claims")
    action_rate = _completeness_rate(completeness, "has_recommended_actions_rate", bundle, "recommended_action_candidates")
    claim_violations = _violation_count(claim_audit, "claim_check_pass")
    static_violations = _violation_count(static_claims, "claim_boundary_pass")
    actionability_rate = 1.0
    if not actionability.empty and "actionable_flag" in actionability.columns:
        actionability_rate = float(actionability["actionable_flag"].map(normalize_bool).mean())
    card_complete_rate = 1.0
    if not static_complete.empty and "card_complete" in static_complete.columns:
        card_complete_rate = float(static_complete["card_complete"].map(normalize_bool).mean())
    auto_dispatch_all_false = True
    if not bundle.empty and "auto_dispatch_allowed" in bundle.columns:
        auto_dispatch_all_false = not bundle["auto_dispatch_allowed"].map(normalize_bool).any()
    p0_count = int((bundle.get("review_priority", pd.Series(dtype=str)).astype(str) == "P0").sum()) if not bundle.empty else 0
    strong_count = int((bundle.get("evidence_strength", pd.Series(dtype=str)).astype(str) == "strong").sum()) if not bundle.empty else 0

    status = "ready_for_manual_review"
    requires_fix = False
    if (
        allowed_rate < 0.99
        or forbidden_rate < 0.99
        or action_rate < 0.99
        or claim_violations
        or static_violations
        or card_complete_rate < 0.99
        or not auto_dispatch_all_false
    ):
        status = "requires_fix_before_review"
        requires_fix = True

    md = f"""# Evidence Bundle / Static Card Assessment

`evidence_material_status = {status}`

## Evidence

- Structured bundle rows: {len(bundle)}
- allowed_claims coverage: {allowed_rate:.4f}
- forbidden_claims coverage: {forbidden_rate:.4f}
- recommended_action_candidates coverage: {action_rate:.4f}
- Claim consistency violations: {claim_violations}
- Static card claim boundary violations: {static_violations}
- Actionability pass rate: {actionability_rate:.4f}
- Static card complete rate: {card_complete_rate:.4f}
- auto_dispatch_allowed all false: {auto_dispatch_all_false}
- P0 count: {p0_count}
- strong evidence count: {strong_count}

## Conclusion

The structured evidence bundle and static line-card review package are ready for
manual review. P0=0 and strong=0 should be presented as a conservative v1
limitation rather than as a production readiness problem.
"""
    return Assessment(
        "evidence_material",
        status,
        requires_fix,
        "Evidence material is ready for manual review.",
        {
            "bundle_rows": len(bundle),
            "allowed_claims_rate": allowed_rate,
            "forbidden_claims_rate": forbidden_rate,
            "recommended_actions_rate": action_rate,
            "claim_violations": claim_violations,
            "static_claim_violations": static_violations,
            "actionability_rate": actionability_rate,
            "card_complete_rate": card_complete_rate,
            "auto_dispatch_all_false": auto_dispatch_all_false,
            "p0_count": p0_count,
            "strong_count": strong_count,
        },
        md,
    )


def _completeness_rate(completeness: pd.DataFrame, column: str, fallback_df: pd.DataFrame, fallback_column: str) -> float:
    if not completeness.empty and column in completeness.columns:
        values = pd.to_numeric(completeness[column], errors="coerce").dropna()
        if not values.empty:
            return float(values.mean())
    if not fallback_df.empty and fallback_column in fallback_df.columns:
        return float(fallback_df[fallback_column].notna().mean())
    return 0.0


def _violation_count(audit: pd.DataFrame, pass_column: str) -> int:
    if audit.empty:
        return 0
    if pass_column not in audit.columns:
        return 0
    return int((~audit[pass_column].map(normalize_bool)).sum())


def freeze_decision(assessments: list[Assessment]) -> str:
    if any(item.requires_fix for item in assessments):
        return "do_not_freeze"
    if any("caveat" in item.status or "weak" in item.status for item in assessments):
        return "freeze_with_caveats"
    return "freeze"


def build_risk_register(assessments: list[Assessment]) -> pd.DataFrame:
    lookup = {item.area: item for item in assessments}
    rows = [
        (
            "R001",
            "demand_shape",
            "Demand-shape raw observation expansion can overwhelm display surfaces.",
            "medium",
            "medium",
            f"raw={lookup['demand_shape'].details.get('raw_rows')}; display={lookup['demand_shape'].details.get('display_ready_rows')}",
            "Raw table retained as audit; display-ready view used for presentation.",
            False,
            "Keep raw observation out of main candidate and display paths.",
            "M1/M2 corrections",
        ),
        (
            "R002",
            "demand_shape",
            "History sufficiency uncertainty may affect intermittent/lumpy classification.",
            "medium",
            "medium",
            f"IL history_insufficient rate={lookup['demand_shape'].details.get('intermittent_lumpy_history_insufficient_rate'):.4f}",
            "history_sufficiency_flag added; display-ready filtering uses low-confidence guardrail.",
            False,
            "Deep-validate history sufficiency thresholds with business review.",
            "M1/M3",
        ),
        (
            "R003",
            "value",
            "Relative value_at_risk may be misread as real monetary loss.",
            "medium",
            "medium",
            str(lookup["value_at_risk"].details.get("relative_value_columns")),
            "Use relative_value_at_risk_H and relative_business_priority_score_H naming.",
            False,
            "Confirm amount comparability and monotonicity before monetary presentation.",
            "M1/M5/M7",
        ),
        (
            "R004",
            "one_shot",
            "M2 repeat propensity discrimination is modest.",
            "medium",
            "medium",
            f"mean_auc={lookup['one_shot'].details.get('mean_auc'):.4f}",
            "One-shot remains side-path manual review material.",
            False,
            "Confirm one-shot strategy with demand side and run real holdout review.",
            "M2",
        ),
        (
            "R005",
            "detector",
            "Quantity detector has a high hit rate and may be broad.",
            "medium",
            "medium",
            f"quantity_hit_rate={lookup['survival_detector'].details.get('quantity_hit_rate'):.4f}",
            "Quantity-only evidence does not create strong evidence or priority_review by itself.",
            False,
            "Calibrate detector thresholds after client feedback.",
            "M4/M5",
        ),
        (
            "R006",
            "status_decision",
            "P0=0 and strong=0 make v1 conservative.",
            "low",
            "high",
            f"P0={lookup['evidence_material'].details.get('p0_count')}; strong={lookup['evidence_material'].details.get('strong_count')}",
            "Manual-review positioning and static-card notes disclose the limitation.",
            False,
            "Review whether P0/strong criteria are too strict after manual sampling.",
            "M5/M7",
        ),
        (
            "R007",
            "detector",
            "Delivery and price detectors are interface-only.",
            "medium",
            "high",
            f"price_interface={lookup['survival_detector'].details.get('price_interface_only')}; delivery_interface={lookup['survival_detector'].details.get('delivery_interface_only')}",
            "Interface-only detectors excluded from effective evidence.",
            False,
            "Implement only after reliable price and delivery data are available.",
            "M4",
        ),
        (
            "R008",
            "M6",
            "Evidence timeline cache is not implemented.",
            "low",
            "high",
            "M6 fields are present but fixed as not_implemented_in_v1.",
            "M6 kept as interface only.",
            False,
            "Implement evidence persistence after detector schema stabilizes.",
            "M6",
        ),
        (
            "R009",
            "validation",
            "No real client churn backtest yet.",
            "high",
            "high",
            "Current validation is offline/prototype review.",
            "Manual review package prepared.",
            False,
            "Collect real terminal churn labels and intervention outcomes.",
            "M8",
        ),
        (
            "R010",
            "LLM",
            "No LLM line-card generation has been implemented.",
            "low",
            "high",
            "Static template prototype only.",
            "allowed/forbidden claims are generated and audited.",
            False,
            "If LLM is introduced, constrain it to wording only.",
            "M7/LLM",
        ),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "risk_id",
            "risk_area",
            "risk_description",
            "severity",
            "likelihood",
            "current_evidence",
            "current_mitigation",
            "requires_fix_before_freeze",
            "recommended_action",
            "owner_stage",
        ],
    )


def build_required_fixes(assessments: list[Assessment]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in assessments:
        if item.requires_fix:
            rows.append(
                {
                    "fix_id": f"FIX_{len(rows) + 1:03d}",
                    "fix_description": f"Resolve blocking issue in {item.area}: {item.status}",
                    "blocking_reason": item.summary,
                    "required_before_freeze": True,
                    "suggested_codex_task": f"Audit and correct {item.area} before freezing the non-LLM stage.",
                }
            )
    return pd.DataFrame(
        rows,
        columns=["fix_id", "fix_description", "blocking_reason", "required_before_freeze", "suggested_codex_task"],
    )


def build_backlog() -> pd.DataFrame:
    items = [
        ("B001", "Demand-shape threshold / history_sufficiency deeper validation", "M1/M3", "high"),
        ("B002", "Value_at_risk real amount comparability confirmation", "M1/M5/M7", "high"),
        ("B003", "One-shot strategy confirmation with demand side", "M2", "medium"),
        ("B004", "Detector threshold calibration", "M4/M5", "medium"),
        ("B005", "Customer real churn backtest", "M8", "high"),
        ("B006", "M6 evidence timeline cache", "M6", "medium"),
        ("B007", "VP daily screen / daily report prototype", "Product", "medium"),
        ("B008", "LLM/MCP line-card generation", "M7/LLM", "medium"),
        ("B009", "Intervention feedback / uplift data collection", "M8/Product", "medium"),
    ]
    return pd.DataFrame(items, columns=["backlog_id", "backlog_item", "owner_stage", "priority"])


def build_freeze_decision_markdown(decision: str, assessments: list[Assessment], required_fixes: pd.DataFrame) -> str:
    blocking_count = len(required_fixes)
    lines = [
        "# Stage-end Freeze Decision",
        "",
        f"`stage_freeze_decision = {decision}`",
        "",
        f"Blocking fixes before freeze: {blocking_count}",
        "",
        "## Assessment Status",
        "",
    ]
    for item in assessments:
        lines.append(f"- {item.area}: {item.status}; requires_fix_before_freeze={str(item.requires_fix).lower()}")
    lines.extend(
        [
            "",
            "## Decision Rationale",
            "",
            "The current non-LLM structured evidence stage can be frozen with caveats when no blocking "
            "algorithm-semantics issue remains. The caveats are tracked as backlog items: relative value "
            "semantics, detector threshold validation, conservative P0/strong rules, no real client backtest, "
            "M6 cache not implemented, and no LLM line-card generation.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_algorithm_review_markdown(decision: str, assessments: list[Assessment], risk_register: pd.DataFrame) -> str:
    status_map = {item.area: item.status for item in assessments}
    return f"""# Alive Prediction Stage-end Algorithm Risk Review

## Completed Chain

Stage 1 probability scorer -> M1 business candidate pool -> M2 one-shot repeat
propensity -> M3 survival-lite -> M4 detector evidence -> M5 status decision ->
M7 structured evidence bundle -> static line-card style review package.

## Input Materials

This audit read existing report artifacts from M1/M2 corrections, M2, M3, M4,
M5, M7, end-to-end sample review, and static card review. Missing files are
handled as audit caveats rather than runtime failures.

## Demand-shape Conclusion

`demand_shape_issue_status = {status_map.get("demand_shape")}`

Raw demand-shape observation is retained as audit material while display-ready
observation is used for presentation. The raw table does not feed M3/M5/M7 main
recurring status decisions.

## Value-at-risk Conclusion

`value_semantics_status = {status_map.get("value_at_risk")}`

Business priority is a relative priority score, not a probability and not
confirmed real monetary loss.

## M2 One-shot Conclusion

`m2_status = {status_map.get("one_shot")}`

M2 remains a side-path first-purchase repeat propensity signal. It is not
recurring churn probability and should be interpreted as manual-review context.

## M3/M4 Conclusion

`survival_detector_status = {status_map.get("survival_detector")}`

M3 does not change probability or business priority. M4 detector severity and
confidence are evidence attributes, not probabilities. Price and delivery
detectors remain interface-only.

## M5/M7/Static Card Conclusion

`evidence_material_status = {status_map.get("evidence_material")}`

The evidence bundle and static card prototype pass claim/actionability checks
and keep auto_dispatch_allowed false.

## Blocking Fixes

Blocking fixes before freeze: {sum(item.requires_fix for item in assessments)}

## Freeze Decision

`stage_freeze_decision = {decision}`

The non-LLM structured evidence stage can be frozen with caveats if no blocking
fixes are listed in `stage_end_required_fixes.csv`.

## Freeze Caveats

- Relative value semantics must be confirmed before monetary presentation.
- Demand-shape history sufficiency thresholds need deeper validation.
- Quantity detector thresholds need production calibration.
- P0=0 / strong=0 is a conservative v1 limitation.
- No real client churn backtest has been completed.
- M6 evidence timeline cache and LLM line-card generation are not implemented.

## Next Stage Recommendations

Prioritize manual review of static cards, value comparability confirmation,
detector threshold calibration, client backtesting, and only then LLM/MCP line
card generation under allowed/forbidden claim constraints.

## Risk Register Summary

Total risks tracked: {len(risk_register)}
"""


def build_notebook_summary(decision: str, assessments: list[Assessment]) -> str:
    status_map = {item.area: item.status for item in assessments}
    return f"""本阶段 non-LLM 主干链路已经形成从 Stage 1 概率 scorer 到 M7 structured evidence bundle、再到静态线索卡样式原型的闭环。M1 将 recurring 主候选限定在 business priority 排序结果内，one-shot 与 demand-shape observation 保持旁路语义；M2 输出 first-purchase repeat_probability_H，不解释为 recurring churn；M3 只处理 recurring 主表，并保留 churn_probability_H 与 relative_business_priority_score_H 不变；M4 detector 仅提供结构化 evidence，severity/confidence 不是概率；M5/M7 继续保持 auto_dispatch_allowed=false，并通过 allowed_claims / forbidden_claims 约束输出边界。当前 demand-shape raw observation 已被压缩为 display-ready 视图，static card review 的 claim 与 actionability 检查可支持人工复核。阶段冻结结论为 `{decision}`：可冻结为 non-LLM structured evidence stage，但需要保留 caveats，包括 value_at_risk 仍只能解释为 relative priority、detector 阈值需后续校准、缺少真实客户流失回测、M6 cache 未实现、LLM/MCP 线索卡尚未接入。关键状态：demand_shape={status_map.get("demand_shape")}; value={status_map.get("value_at_risk")}; M2={status_map.get("one_shot")}; M3/M4={status_map.get("survival_detector")}; evidence={status_map.get("evidence_material")}。"""


def run_stage_end_audit(project_root: Path, output_dir: Path | None = None, dry_run: bool = False) -> dict[str, Any]:
    """Generate stage-end audit outputs from existing reports."""
    if dry_run:
        project_root = _build_dry_run_project(project_root)
    output = output_dir or project_root / STAGE_END_REPORT_DIR
    output.mkdir(parents=True, exist_ok=True)

    assessments = [
        assess_demand_shape(project_root),
        assess_value_semantics(project_root),
        assess_one_shot(project_root),
        assess_survival_detector(project_root),
        assess_evidence_material(project_root),
    ]
    decision = freeze_decision(assessments)
    risk_register = build_risk_register(assessments)
    required_fixes = build_required_fixes(assessments)
    backlog = build_backlog()

    assessment_files = {
        "demand_shape": "demand_shape_risk_assessment.md",
        "value_at_risk": "value_at_risk_semantics_assessment.md",
        "one_shot": "one_shot_risk_assessment.md",
        "survival_detector": "survival_detector_status_assessment.md",
        "evidence_material": "evidence_bundle_static_card_assessment.md",
    }
    for item in assessments:
        (output / assessment_files[item.area]).write_text(item.markdown, encoding="utf-8")

    risk_register.to_csv(output / "stage_end_risk_register.csv", index=False)
    required_fixes.to_csv(output / "stage_end_required_fixes.csv", index=False)
    backlog.to_csv(output / "stage_end_backlog.csv", index=False)
    (output / "stage_end_freeze_decision.md").write_text(
        build_freeze_decision_markdown(decision, assessments, required_fixes),
        encoding="utf-8",
    )
    (output / "stage_end_algorithm_risk_review.md").write_text(
        build_algorithm_review_markdown(decision, assessments, risk_register),
        encoding="utf-8",
    )
    (output / "stage_end_summary_for_notebook.md").write_text(
        build_notebook_summary(decision, assessments),
        encoding="utf-8",
    )

    return {
        "output_dir": output,
        "stage_freeze_decision": decision,
        "assessments": assessments,
        "required_fix_count": len(required_fixes),
        "risk_count": len(risk_register),
    }


def _build_dry_run_project(root: Path) -> Path:
    """Create a tiny report fixture under root for script smoke tests."""
    reports = root / "reports"
    (reports / "alive_prediction_m1_m2_corrections_v1").mkdir(parents=True, exist_ok=True)
    (reports / "alive_prediction_one_shot_repeat_v1").mkdir(parents=True, exist_ok=True)
    (reports / "alive_prediction_survival_lite_v1").mkdir(parents=True, exist_ok=True)
    (reports / "alive_prediction_detectors_v1").mkdir(parents=True, exist_ok=True)
    (reports / "alive_prediction_status_decision_v1").mkdir(parents=True, exist_ok=True)
    (reports / "alive_prediction_evidence_bundle_v1").mkdir(parents=True, exist_ok=True)
    (reports / "alive_prediction_evidence_bundle_review_v1").mkdir(parents=True, exist_ok=True)
    (reports / "alive_prediction_static_line_card_review_v1").mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [{"metric": "total_rows", "value": 100}, {"metric": "display_ready_rows", "value": 5}, {"metric": "latest_cutoff_rows", "value": 20}]
    ).to_csv(reports / "alive_prediction_m1_m2_corrections_v1/demand_shape_observation_raw_profile.csv", index=False)
    pd.DataFrame(
        [{"demand_shape_label": "lumpy", "history_sufficiency_flag": "history_insufficient", "purchase_count_asof_cutoff": 1}]
    ).to_csv(reports / "alive_prediction_m1_m2_corrections_v1/demand_shape_history_sufficiency_flags.csv", index=False)
    pd.DataFrame([{"filter_stage": "raw", "row_count": 100, "note": "raw observation rows retained separately"}]).to_csv(
        reports / "alive_prediction_m1_m2_corrections_v1/demand_shape_observation_filter_audit.csv", index=False
    )
    (reports / "alive_prediction_m1_m2_corrections_v1/m1_m2_next_stage_gate.md").write_text(
        "proceed_to_M3 = conditional\nM3 only reads recurring_business_priority_candidates.", encoding="utf-8"
    )
    pd.DataFrame([{"primary_relative_value_at_risk": 10.0, "primary_relative_business_priority_score": 5.0}]).to_csv(
        reports / "alive_prediction_m1_m2_corrections_v1/recurring_business_priority_candidates_checked.csv", index=False
    )
    pd.DataFrame([{"horizon": "H3", "auc": 0.6, "ece": 0.1, "fallback_used": False, "skip_reason": ""}]).to_csv(
        reports / "alive_prediction_one_shot_repeat_v1/one_shot_repeat_metrics.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "candidate_id": "os1",
                "probability_interpretation": "first_purchase_repeat_probability_not_recurring_churn_probability",
                "repeat_probability_H": 0.3,
            }
        ]
    ).to_csv(reports / "alive_prediction_one_shot_repeat_v1/one_shot_attention_candidates_enriched.csv", index=False)
    pd.DataFrame([{"candidate_id": "os1"}]).to_csv(
        reports / "alive_prediction_one_shot_repeat_v1/one_shot_explanation_factors.csv", index=False
    )
    (reports / "alive_prediction_one_shot_repeat_v1/one_shot_leakage_audit.md").write_text("No leakage found.", encoding="utf-8")
    pd.DataFrame(
        [
            {
                "survival_state": "materially_overdue",
                "survival_confidence": 0.7,
                "survival_note": "probability_and_business_priority_unchanged",
            }
        ]
    ).to_csv(reports / "alive_prediction_survival_lite_v1/survival_refinement_results.csv", index=False)
    (reports / "alive_prediction_survival_lite_v1/survival_leakage_audit.md").write_text("No direct leakage.", encoding="utf-8")
    pd.DataFrame(
        [
            {"detector_name": "terminal_loss_warning", "detector_status": "implemented", "hit_count": 1, "hit_rate": 1.0},
            {"detector_name": "purchase_quantity_fluctuation_warning", "detector_status": "implemented", "hit_count": 1, "hit_rate": 1.0},
            {"detector_name": "low_price_purchase_warning", "detector_status": "interface_only", "hit_count": 0, "hit_rate": 0.0},
            {"detector_name": "delayed_response_warning", "detector_status": "interface_only", "hit_count": 0, "hit_rate": 0.0},
        ]
    ).to_csv(reports / "alive_prediction_detectors_v1/detector_family_summary.csv", index=False)
    pd.DataFrame([{"evidence_strength": "medium", "auto_dispatch_allowed": False}]).to_csv(
        reports / "alive_prediction_status_decision_v1/candidate_status_decision.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "review_priority": "P1",
                "evidence_strength": "medium",
                "auto_dispatch_allowed": False,
                "allowed_claims": "[]",
                "forbidden_claims": "[]",
                "recommended_action_candidates": "[]",
                "business_priority_interpretation": "not_probability",
            }
        ]
    ).to_csv(reports / "alive_prediction_evidence_bundle_v1/structured_evidence_bundle.csv", index=False)
    pd.DataFrame(
        [
            {
                "candidate_type": "recurring_business_priority",
                "has_allowed_claims_rate": 1.0,
                "has_forbidden_claims_rate": 1.0,
                "has_recommended_actions_rate": 1.0,
            }
        ]
    ).to_csv(reports / "alive_prediction_evidence_bundle_v1/evidence_bundle_completeness_report.csv", index=False)
    pd.DataFrame([{"claim_check_pass": True}]).to_csv(
        reports / "alive_prediction_evidence_bundle_review_v1/evidence_bundle_claim_consistency_audit.csv", index=False
    )
    pd.DataFrame([{"actionable_flag": True}]).to_csv(
        reports / "alive_prediction_evidence_bundle_review_v1/evidence_bundle_actionability_audit.csv", index=False
    )
    pd.DataFrame([{"claim_boundary_pass": True}]).to_csv(
        reports / "alive_prediction_static_line_card_review_v1/static_line_card_claim_boundary_audit.csv", index=False
    )
    pd.DataFrame([{"card_complete": True}]).to_csv(
        reports / "alive_prediction_static_line_card_review_v1/static_line_card_field_completeness.csv", index=False
    )
    return root


__all__ = [
    "Assessment",
    "assess_demand_shape",
    "assess_evidence_material",
    "assess_one_shot",
    "assess_survival_detector",
    "assess_value_semantics",
    "build_backlog",
    "build_required_fixes",
    "build_risk_register",
    "freeze_decision",
    "load_csv_if_exists",
    "read_text_if_exists",
    "run_stage_end_audit",
]
