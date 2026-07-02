"""Read-only helpers for the alive prediction M1-M7 refinement story notebook.

This module only reads existing CSV/Markdown reports under ``reports/``.
It does not train models, run M1-M7 scripts, call LLMs, or read parquet/cache
artifacts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


REPORT_GROUPS: dict[str, list[str]] = {
    "stage1_probability": [
        "reports/alive_prediction_calibration_v2/calibration_v2_summary.md",
        "reports/alive_prediction_calibration_v2/calibration_v2_metrics_by_fold.csv",
        "reports/alive_prediction_calibration_v2/probability_candidate_v1_decision_v2.csv",
    ],
    "m1_candidate_pool": [
        "reports/alive_prediction_candidate_pool_v1/recurring_business_priority_candidates_by_horizon.csv",
        "reports/alive_prediction_candidate_pool_v1/recurring_business_priority_candidates.csv",
        "reports/alive_prediction_candidate_pool_v1/one_shot_attention_candidates.csv",
        "reports/alive_prediction_candidate_pool_v1/demand_shape_observation_candidates.csv",
        "reports/alive_prediction_candidate_pool_v1/candidate_pool_selection_audit.csv",
    ],
    "m1_m2_corrections": [
        "reports/alive_prediction_m1_m2_corrections_v1/demand_shape_observation_raw_profile.csv",
        "reports/alive_prediction_m1_m2_corrections_v1/demand_shape_observation_display_ready.csv",
        "reports/alive_prediction_m1_m2_corrections_v1/demand_shape_history_sufficiency_flags.csv",
        "reports/alive_prediction_m1_m2_corrections_v1/m1_m2_next_stage_gate.md",
    ],
    "m2_one_shot": [
        "reports/alive_prediction_one_shot_repeat_v1/one_shot_repeat_metrics.csv",
        "reports/alive_prediction_one_shot_repeat_v1/one_shot_attention_candidates_enriched.csv",
        "reports/alive_prediction_one_shot_repeat_v1/one_shot_explanation_factors.csv",
        "reports/alive_prediction_one_shot_repeat_v1/one_shot_group_prior_report.csv",
        "reports/alive_prediction_one_shot_repeat_v1/one_shot_repeat_v1_summary.md",
    ],
    "m3_survival_lite": [
        "reports/alive_prediction_survival_lite_v1/survival_refinement_results.csv",
        "reports/alive_prediction_survival_lite_v1/survival_state_distribution.csv",
        "reports/alive_prediction_survival_lite_v1/survival_history_sufficiency_report.csv",
        "reports/alive_prediction_survival_lite_v1/survival_demand_shape_route_report.csv",
        "reports/alive_prediction_survival_lite_v1/survival_lite_v1_summary.md",
        "reports/alive_prediction_survival_lite_v1/survival_leakage_audit.md",
    ],
    "m4_detectors": [
        "reports/alive_prediction_detectors_v1/detector_evidence_results.csv",
        "reports/alive_prediction_detectors_v1/detector_family_summary.csv",
        "reports/alive_prediction_detectors_v1/detector_semantics_audit.md",
    ],
    "m5_status_decision": [
        "reports/alive_prediction_status_decision_v1/candidate_status_decision.csv",
        "reports/alive_prediction_status_decision_v1/status_decision_distribution.csv",
        "reports/alive_prediction_status_decision_v1/review_priority_distribution.csv",
        "reports/alive_prediction_status_decision_v1/evidence_strength_distribution.csv",
        "reports/alive_prediction_status_decision_v1/status_decision_semantics_audit.md",
    ],
    "m7_evidence_bundle": [
        "reports/alive_prediction_evidence_bundle_v1/structured_evidence_bundle.csv",
        "reports/alive_prediction_evidence_bundle_v1/evidence_bundle_completeness_report.csv",
        "reports/alive_prediction_evidence_bundle_v1/evidence_bundle_semantics_audit.md",
        "reports/alive_prediction_evidence_bundle_v1/evidence_bundle_next_stage_readiness.md",
    ],
    "bundle_review": [
        "reports/alive_prediction_evidence_bundle_review_v1/evidence_bundle_review_summary.md",
        "reports/alive_prediction_evidence_bundle_review_v1/evidence_bundle_stratified_sample.csv",
        "reports/alive_prediction_evidence_bundle_review_v1/evidence_bundle_claim_consistency_audit.csv",
        "reports/alive_prediction_evidence_bundle_review_v1/evidence_bundle_actionability_audit.csv",
        "reports/alive_prediction_evidence_bundle_review_v1/evidence_bundle_llm_readiness_report.md",
    ],
    "static_line_card_review": [
        "reports/alive_prediction_static_line_card_review_v1/static_line_card_review_summary.md",
        "reports/alive_prediction_static_line_card_review_v1/static_line_card_sample_index.csv",
        "reports/alive_prediction_static_line_card_review_v1/static_line_card_field_completeness.csv",
        "reports/alive_prediction_static_line_card_review_v1/static_line_card_claim_boundary_audit.csv",
        "reports/alive_prediction_static_line_card_review_v1/static_line_card_samples.md",
        "reports/alive_prediction_static_line_card_review_v1/static_line_card_samples.html",
        "reports/alive_prediction_static_line_card_review_v1/static_line_card_llm_readiness_note.md",
    ],
}


def warning_frame(message: str, *, path: Path | None = None) -> pd.DataFrame:
    row: dict[str, Any] = {"warning": message}
    if path is not None:
        row["path"] = str(path)
    return pd.DataFrame([row])


def load_csv_if_exists(path: Path) -> pd.DataFrame | None:
    """Read a CSV report, returning ``None`` when absent."""
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception as exc:  # pragma: no cover - defensive notebook helper.
        return warning_frame(f"failed_to_read_csv:{exc!r}", path=path)


def read_md_head(path: Path, max_chars: int = 3000) -> str:
    """Read a short Markdown excerpt without raising in notebooks."""
    if not path.exists():
        return f"[missing] {path}"
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except Exception as exc:  # pragma: no cover - defensive notebook helper.
        return f"[failed_to_read_markdown] {path}: {exc!r}"


def missing_files_report(project_root: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for group, rel_paths in REPORT_GROUPS.items():
        for rel in rel_paths:
            path = project_root / rel
            rows.append(
                {
                    "group": group,
                    "path": rel,
                    "exists": path.exists(),
                    "file_size": path.stat().st_size if path.exists() else 0,
                }
            )
    return pd.DataFrame(rows)


def stage_overview(project_root: Path) -> pd.DataFrame:
    missing = missing_files_report(project_root)
    rows: list[dict[str, Any]] = []
    for group, part in missing.groupby("group", sort=False):
        rows.append(
            {
                "stage": group,
                "available_files": int(part["exists"].sum()),
                "expected_files": int(len(part)),
                "missing_files": ", ".join(part.loc[~part["exists"], "path"].tolist()),
            }
        )
    return pd.DataFrame(rows)


def row_count(project_root: Path, rel_path: str) -> int | None:
    df = load_csv_if_exists(project_root / rel_path)
    if df is None:
        return None
    return int(len(df))


def table_counts(project_root: Path, rel_paths: dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"table": name, "row_count": row_count(project_root, rel)} for name, rel in rel_paths.items()]
    )


def value_counts_table(df: pd.DataFrame | None, column: str, *, label: str | None = None) -> pd.DataFrame:
    if df is None:
        return warning_frame(f"missing_table_for:{column}")
    if column not in df.columns:
        return warning_frame(f"missing_column:{column}")
    out = df[column].fillna("__MISSING__").astype(str).value_counts(dropna=False).reset_index()
    out.columns = [label or column, "row_count"]
    out["share"] = out["row_count"] / max(len(df), 1)
    return out


def numeric_summary(df: pd.DataFrame | None, columns: list[str]) -> pd.DataFrame:
    if df is None:
        return warning_frame("missing_table")
    rows: list[dict[str, Any]] = []
    for col in columns:
        if col not in df.columns:
            rows.append({"metric": col, "warning": "missing_column"})
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        rows.append(
            {
                "metric": col,
                "count": int(series.notna().sum()),
                "mean": series.mean(),
                "p50": series.quantile(0.5),
                "p90": series.quantile(0.9),
                "max": series.max(),
            }
        )
    return pd.DataFrame(rows)


def bool_all_false(df: pd.DataFrame | None, column: str) -> bool | None:
    if df is None or column not in df.columns:
        return None
    values = df[column]
    if values.dtype == bool:
        return bool((~values.fillna(False)).all())
    return bool(~values.fillna(False).astype(str).str.lower().isin(["true", "1", "yes", "y"]).any())


def m1_summary(project_root: Path) -> dict[str, pd.DataFrame]:
    base = "reports/alive_prediction_candidate_pool_v1"
    by_h = load_csv_if_exists(project_root / f"{base}/recurring_business_priority_candidates_by_horizon.csv")
    main = load_csv_if_exists(project_root / f"{base}/recurring_business_priority_candidates.csv")
    one = load_csv_if_exists(project_root / f"{base}/one_shot_attention_candidates.csv")
    obs = load_csv_if_exists(project_root / f"{base}/demand_shape_observation_candidates.csv")
    audit = load_csv_if_exists(project_root / f"{base}/candidate_pool_selection_audit.csv")
    return {
        "counts": table_counts(
            project_root,
            {
                "recurring_by_horizon": f"{base}/recurring_business_priority_candidates_by_horizon.csv",
                "recurring_main": f"{base}/recurring_business_priority_candidates.csv",
                "one_shot_attention": f"{base}/one_shot_attention_candidates.csv",
                "raw_demand_shape_observation": f"{base}/demand_shape_observation_candidates.csv",
            },
        ),
        "selected_horizons": value_counts_table(main, "selected_horizons"),
        "primary_horizon": value_counts_table(main, "primary_horizon"),
        "selection_reason": value_counts_table(by_h, "selection_reason"),
        "audit": audit.head(30) if audit is not None else warning_frame("candidate_pool_selection_audit missing"),
    }


def correction_summary(project_root: Path) -> dict[str, pd.DataFrame | str]:
    base = "reports/alive_prediction_m1_m2_corrections_v1"
    raw_profile = load_csv_if_exists(project_root / f"{base}/demand_shape_observation_raw_profile.csv")
    display_ready = load_csv_if_exists(project_root / f"{base}/demand_shape_observation_display_ready.csv")
    flags = load_csv_if_exists(project_root / f"{base}/demand_shape_history_sufficiency_flags.csv")
    raw_rows = None
    latest_rows = None
    if raw_profile is not None and not raw_profile.empty:
        row = raw_profile.iloc[0]
        raw_rows = row.get("total_rows")
        latest_rows = row.get("latest_cutoff_rows")
    display_rows = len(display_ready) if display_ready is not None else None
    compression = (display_rows / raw_rows) if raw_rows not in (None, 0) and display_rows is not None else None
    return {
        "counts": pd.DataFrame(
            [
                {
                    "raw_observation_rows": raw_rows,
                    "display_ready_rows": display_rows,
                    "compression_ratio_display_over_raw": compression,
                    "latest_cutoff_rows": latest_rows,
                }
            ]
        ),
        "history_sufficiency": value_counts_table(flags, "history_sufficiency_flag"),
        "gate": read_md_head(project_root / f"{base}/m1_m2_next_stage_gate.md", 1600),
    }


def detector_hit_counts(detectors: pd.DataFrame | None) -> pd.DataFrame:
    if detectors is None:
        return warning_frame("detector_evidence_results missing")
    if "detector_name" not in detectors.columns or "hit_flag" not in detectors.columns:
        return warning_frame("detector evidence lacks detector_name/hit_flag")
    hit = detectors["hit_flag"]
    if hit.dtype != bool:
        hit = hit.fillna(False).astype(str).str.lower().isin(["true", "1", "yes", "y"])
    out = detectors.assign(_hit=hit).groupby("detector_name", dropna=False)["_hit"].sum().reset_index()
    out.columns = ["detector_name", "hit_count"]
    return out.sort_values("hit_count", ascending=False)


def claim_coverage(df: pd.DataFrame | None, columns: list[str]) -> pd.DataFrame:
    if df is None:
        return warning_frame("missing_table")
    rows = []
    for col in columns:
        if col not in df.columns:
            rows.append({"field": col, "coverage": None, "warning": "missing_column"})
        else:
            rows.append({"field": col, "coverage": float(df[col].fillna("").astype(str).ne("").mean())})
    return pd.DataFrame(rows)


def extract_static_card_excerpt(project_root: Path, max_chars: int = 5000) -> str:
    path = project_root / "reports/alive_prediction_static_line_card_review_v1/static_line_card_samples.md"
    text = read_md_head(path, max_chars)
    if text.startswith("[missing]"):
        return text
    # Keep the first card and the document heading.
    marker = "\n## ["
    first = text.find(marker)
    if first == -1:
        return text[:max_chars]
    second = text.find(marker, first + len(marker))
    return text[: second if second != -1 else max_chars]


def final_boundary_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"item": "stage_closed_without_llm", "value": "true"},
            {"item": "probability_candidate_v1", "value": "logistic_regression + frequency_decay_v1 + raw"},
            {"item": "business_usable_probability_baseline", "value": "true"},
            {"item": "m6_cache_implemented", "value": "false"},
            {"item": "auto_dispatch_allowed", "value": "false_for_all_rows"},
            {"item": "static_line_cards_are_final_cards", "value": "false"},
        ]
    )
