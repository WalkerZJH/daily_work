"""Build row-level closed-window backtest frames for alive prediction.

This module only joins existing predictions with existing labels or read-only
feature snapshots. It does not train models, tune thresholds, save models, call
LLMs, or modify M1-M7 outputs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


HORIZONS = [3, 6, 12]
ENTITY_COLS = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source"]
JOIN_ENTITY_COLS = ["manufacturer_code", "hospital_code", "drug_group"]

RECURRING_COLUMNS = [
    "manufacturer_code",
    "hospital_code",
    "drug_group",
    "drug_group_source",
    "cutoff_month",
    "horizon",
    "churn_probability_H",
    "prediction_source",
    "probability_candidate_version",
    "relative_value_at_risk_H",
    "relative_business_priority_score_H",
    "label_alive_H",
    "label_die_H",
    "label_window_closed",
    "label_window_start",
    "label_window_end",
    "max_observed_purchase_date",
    "rank_probability_global",
    "rank_business_priority_global",
    "rank_probability_within_manufacturer",
    "rank_business_priority_within_manufacturer",
    "in_recurring_business_priority_candidates",
    "final_candidate_status",
    "review_priority",
    "evidence_strength",
    "survival_state",
    "demand_shape_label",
    "demand_shape_route",
    "detector_hit_summary",
]

ONE_SHOT_COLUMNS = [
    "manufacturer_code",
    "hospital_code",
    "drug_group",
    "drug_group_source",
    "first_purchase_month",
    "horizon",
    "repeat_probability_H",
    "one_shot_non_repeat_risk_H",
    "selected_attention_score",
    "selected_attention_policy",
    "label_repeat_H",
    "label_non_repeat_H",
    "label_window_closed",
    "label_window_start",
    "label_window_end",
    "max_observed_purchase_date",
    "rank_repeat_probability",
    "rank_non_repeat_risk",
    "rank_selected_attention",
    "probability_interpretation",
    "prediction_source",
    "m2_model_version",
]


def read_csv_or_empty(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, **kwargs)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def read_parquet_or_empty(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(path, columns=columns)
    except (FileNotFoundError, ValueError, ImportError):
        return pd.DataFrame()


def write_csv(path: Path, df: pd.DataFrame, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is not None:
        out = df.copy()
        for col in columns:
            if col not in out.columns:
                out[col] = np.nan
        out = out[columns]
    else:
        out = df
    out.to_csv(path, index=False, encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def to_month_str(series_or_value: Any) -> Any:
    if isinstance(series_or_value, pd.Series):
        return pd.to_datetime(series_or_value, errors="coerce").dt.to_period("M").astype(str)
    ts = pd.to_datetime(series_or_value, errors="coerce")
    if pd.isna(ts):
        return np.nan
    return ts.to_period("M").strftime("%Y-%m")


def month_end(month_like: Any) -> pd.Timestamp:
    ts = pd.to_datetime(str(month_like), errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    return ts.to_period("M").to_timestamp("M")


def add_months_month_end(month_like: Any, months: int) -> pd.Timestamp:
    start = month_end(month_like)
    if pd.isna(start):
        return pd.NaT
    return (start.to_period("M") + int(months)).to_timestamp("M")


def normalize_horizon(value: Any) -> int | None:
    if pd.isna(value):
        return None
    text = str(value).strip().upper()
    if text.startswith("H"):
        text = text[1:]
    try:
        return int(float(text))
    except ValueError:
        return None


def horizon_label(value: Any) -> str:
    horizon = normalize_horizon(value)
    return f"H{horizon}" if horizon is not None else str(value)


def closed_window_flag(label_window_end: Any, max_observed_purchase_date: Any) -> bool:
    end = pd.to_datetime(label_window_end, errors="coerce")
    max_date = pd.to_datetime(max_observed_purchase_date, errors="coerce")
    if pd.isna(end) or pd.isna(max_date):
        return False
    return bool(end <= max_date)


def recurring_label_for_window(
    cutoff_month: Any,
    future_purchase_months: list[Any],
    horizon: int,
    max_observed_purchase_date: Any,
) -> dict[str, Any]:
    start = month_end(cutoff_month)
    end = add_months_month_end(cutoff_month, horizon)
    closed = closed_window_flag(end, max_observed_purchase_date)
    purchases = pd.to_datetime(pd.Series(future_purchase_months), errors="coerce").dropna()
    alive = int(((purchases > start) & (purchases <= end)).any()) if closed else np.nan
    die = 1 - alive if closed else np.nan
    return {
        "label_alive_H": alive,
        "label_die_H": die,
        "label_window_closed": closed,
        "label_window_start": start,
        "label_window_end": end,
    }


def one_shot_repeat_label(
    first_purchase_month: Any,
    purchase_count_at_window_end: Any,
    horizon: int,
    max_observed_purchase_date: Any,
) -> dict[str, Any]:
    start = month_end(first_purchase_month)
    end = add_months_month_end(first_purchase_month, horizon)
    closed = closed_window_flag(end, max_observed_purchase_date)
    count = pd.to_numeric(pd.Series([purchase_count_at_window_end]), errors="coerce").iloc[0]
    repeat = int(count >= 2) if closed and not pd.isna(count) else np.nan
    non_repeat = 1 - repeat if closed and not pd.isna(repeat) else np.nan
    return {
        "label_repeat_H": repeat,
        "label_non_repeat_H": non_repeat,
        "label_window_closed": closed,
        "label_window_start": start,
        "label_window_end": end,
    }


def _long_alive_labels(labels: pd.DataFrame, max_observed_purchase_date: pd.Timestamp) -> pd.DataFrame:
    if labels.empty:
        return pd.DataFrame()
    base = labels.copy()
    if "drug_group_source" not in base.columns:
        base["drug_group_source"] = "drug_code"
    base["_cutoff_period"] = pd.to_datetime(base["cutoff_month"], errors="coerce").dt.to_period("M")
    base["cutoff_month"] = base["_cutoff_period"].astype(str)
    rows = []
    for horizon in HORIZONS:
        alive_col = f"label_alive_H{horizon}"
        die_col = f"label_die_H{horizon}"
        if alive_col not in base.columns or die_col not in base.columns:
            continue
        part = base[ENTITY_COLS + ["cutoff_month", alive_col, die_col]].copy()
        part = part.rename(columns={alive_col: "label_alive_H", die_col: "label_die_H"})
        part["horizon"] = f"H{horizon}"
        periods = pd.PeriodIndex(part["cutoff_month"], freq="M")
        part["label_window_start"] = periods.to_timestamp(freq="M")
        part["label_window_end"] = (periods + horizon).to_timestamp(freq="M")
        part["max_observed_purchase_date"] = max_observed_purchase_date
        part["label_window_closed"] = part["label_window_end"].le(max_observed_purchase_date) & part["label_die_H"].notna()
        rows.append(part)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _rank_within_group(df: pd.DataFrame, score_col: str, group_cols: list[str]) -> pd.Series:
    if score_col not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return df.groupby(group_cols, dropna=False)[score_col].rank(method="first", ascending=False)


def build_detector_hit_summary(detector_v1: pd.DataFrame, detector_v2: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for source, df in [("v1", detector_v1), ("v2", detector_v2)]:
        if df.empty or "candidate_id" not in df.columns:
            continue
        work = df.copy()
        work["source"] = source
        hit = work[work.get("hit_flag", False).astype(bool)].copy()
        if hit.empty:
            continue
        hit["summary_part"] = hit["detector_name"].astype(str) + ":" + hit.get("reason_code", "").fillna("").astype(str)
        frames.append(
            hit.groupby("candidate_id", dropna=False)["summary_part"]
            .apply(lambda s: ";".join(s.astype(str).head(5)))
            .reset_index()
            .rename(columns={"summary_part": "detector_hit_summary"})
        )
    if not frames:
        return pd.DataFrame(columns=["candidate_id", "detector_hit_summary"])
    out = pd.concat(frames, ignore_index=True)
    return (
        out.groupby("candidate_id", dropna=False)["detector_hit_summary"]
        .apply(lambda s: ";".join([x for x in s.astype(str) if x]))
        .reset_index()
    )


def build_recurring_backtest_frame(
    candidate_by_horizon: pd.DataFrame,
    alive_labels: pd.DataFrame,
    status_decision: pd.DataFrame,
    detector_v1: pd.DataFrame,
    detector_v2: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    if candidate_by_horizon.empty:
        return pd.DataFrame(columns=RECURRING_COLUMNS), "candidate_predictions_missing"

    pred = candidate_by_horizon.copy()
    pred["drug_group_source"] = pred.get("drug_group_source", "drug_code").fillna("drug_code")
    pred["cutoff_month"] = to_month_str(pred["cutoff_month"])
    pred["horizon"] = pred["horizon"].map(horizon_label)
    pred["prediction_source"] = "m1_candidate_level_prediction"
    pred["probability_candidate_version"] = pred.get(
        "probability_candidate_version", "logistic_regression + frequency_decay_v1 + raw"
    )

    max_cutoff = pd.to_datetime(alive_labels["cutoff_month"], errors="coerce").max() if not alive_labels.empty else pd.NaT
    max_horizon = max(HORIZONS)
    # The alive label artifact already contains H12 labels through the latest cutoff.
    # Use this inferred observable horizon for closure audit.
    max_observed = (max_cutoff.to_period("M") + max_horizon).to_timestamp("M") if not pd.isna(max_cutoff) else pd.NaT
    labels_long = _long_alive_labels(alive_labels, max_observed)
    if labels_long.empty:
        frame = pred.copy()
        frame["label_alive_H"] = np.nan
        frame["label_die_H"] = np.nan
        frame["label_window_closed"] = False
        frame["label_window_start"] = frame["cutoff_month"].map(month_end)
        frame["label_window_end"] = frame.apply(lambda r: add_months_month_end(r["cutoff_month"], normalize_horizon(r["horizon"]) or 0), axis=1)
        frame["max_observed_purchase_date"] = max_observed
        label_source = "label_artifact_missing"
    else:
        frame = pred.merge(labels_long, on=ENTITY_COLS + ["cutoff_month", "horizon"], how="left")
        frame["label_window_closed"] = frame["label_window_closed"].fillna(False).astype(bool)
        label_source = "candidate_level_join_existing_alive_labels"

    frame["rank_probability_global"] = _rank_within_group(frame, "churn_probability_H", ["cutoff_month", "horizon"])
    frame["rank_business_priority_global"] = _rank_within_group(
        frame, "relative_business_priority_score_H", ["cutoff_month", "horizon"]
    )
    frame["rank_probability_within_manufacturer"] = _rank_within_group(
        frame, "churn_probability_H", ["cutoff_month", "horizon", "manufacturer_code"]
    )
    frame["rank_business_priority_within_manufacturer"] = _rank_within_group(
        frame, "relative_business_priority_score_H", ["cutoff_month", "horizon", "manufacturer_code"]
    )
    frame["in_recurring_business_priority_candidates"] = True

    if not status_decision.empty:
        status = status_decision[status_decision.get("candidate_type") == "recurring_business_priority"].copy()
        status["cutoff_month"] = to_month_str(status["cutoff_month"])
        status["horizon"] = status["horizon"].map(horizon_label)
        keep = [
            "manufacturer_code",
            "hospital_code",
            "drug_group",
            "drug_group_source",
            "cutoff_month",
            "horizon",
            "final_candidate_status",
            "review_priority",
            "evidence_strength",
            "survival_state",
            "demand_shape_label",
            "demand_shape_route",
        ]
        status = status[[c for c in keep if c in status.columns]].drop_duplicates(
            [c for c in keep[:6] if c in status.columns]
        )
        frame = frame.merge(status, on=ENTITY_COLS + ["cutoff_month", "horizon"], how="left", suffixes=("", "_status"))

    detector_summary = build_detector_hit_summary(detector_v1, detector_v2)
    if "candidate_id" in frame.columns and not detector_summary.empty:
        frame = frame.merge(detector_summary, on="candidate_id", how="left")
    elif "detector_hit_summary" not in frame.columns:
        frame["detector_hit_summary"] = np.nan

    return frame, label_source


def build_one_shot_repeat_backtest_frame(
    one_shot_enriched: pd.DataFrame,
    feature_snapshots: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    if one_shot_enriched.empty:
        return pd.DataFrame(columns=ONE_SHOT_COLUMNS), "one_shot_predictions_missing"

    pred = one_shot_enriched.copy()
    pred["drug_group_source"] = pred.get("drug_group_source", "drug_code").fillna("drug_code")
    pred["first_purchase_month"] = to_month_str(pred["first_purchase_month"])
    pred["horizon"] = pred["horizon"].map(horizon_label)
    pred["label_window_start"] = pred["first_purchase_month"].map(month_end)
    pred["label_window_end"] = pred.apply(
        lambda r: add_months_month_end(r["first_purchase_month"], normalize_horizon(r["horizon"]) or 0), axis=1
    )

    if feature_snapshots.empty:
        pred["max_observed_purchase_date"] = pd.NaT
        pred["label_window_closed"] = False
        pred["label_repeat_H"] = np.nan
        pred["label_non_repeat_H"] = np.nan
        label_source = "feature_snapshots_missing"
    else:
        snap = feature_snapshots.copy()
        snap["cutoff_month"] = to_month_str(snap["cutoff_month"])
        snap["cutoff_month_end"] = snap["cutoff_month"].map(month_end)
        max_observed = pd.to_datetime(snap["cutoff_month_end"], errors="coerce").max()
        snap = snap[JOIN_ENTITY_COLS + ["cutoff_month", "purchase_count_asof_cutoff"]].drop_duplicates(
            JOIN_ENTITY_COLS + ["cutoff_month"]
        )
        pred["label_window_end_month"] = pred["label_window_end"].dt.to_period("M").astype(str)
        pred = pred.merge(
            snap,
            left_on=JOIN_ENTITY_COLS + ["label_window_end_month"],
            right_on=JOIN_ENTITY_COLS + ["cutoff_month"],
            how="left",
            suffixes=("", "_snapshot"),
        )
        pred["max_observed_purchase_date"] = max_observed
        pred["label_window_closed"] = pred["label_window_end"].le(max_observed)
        counts = pd.to_numeric(pred["purchase_count_asof_cutoff"], errors="coerce")
        pred["label_repeat_H"] = np.where(pred["label_window_closed"] & counts.notna(), (counts >= 2).astype(int), np.nan)
        pred["label_non_repeat_H"] = np.where(pred["label_window_closed"] & counts.notna(), 1 - pred["label_repeat_H"], np.nan)
        pred = pred.drop(columns=[c for c in ["cutoff_month_snapshot", "label_window_end_month", "purchase_count_asof_cutoff"] if c in pred.columns])
        label_source = "candidate_level_join_feature_snapshot_purchase_count"

    pred["rank_repeat_probability"] = _rank_within_group(pred, "repeat_probability_H", ["horizon"])
    pred["rank_non_repeat_risk"] = _rank_within_group(pred, "one_shot_non_repeat_risk_H", ["horizon"])
    pred["rank_selected_attention"] = _rank_within_group(pred, "selected_attention_score", ["horizon"])
    pred["prediction_source"] = "m2_candidate_level_one_shot_enriched"
    pred["m2_model_version"] = pred.get("model_confidence", "prototype_logistic")
    return pred, label_source


def label_closure_audit(recurring: pd.DataFrame, one_shot: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for frame_name, frame, cutoff_col in [
        ("recurring", recurring, "cutoff_month"),
        ("one_shot", one_shot, "first_purchase_month"),
    ]:
        if frame.empty:
            continue
        for (horizon, cutoff), part in frame.groupby(["horizon", cutoff_col], dropna=False):
            closed = part["label_window_closed"].astype(bool) if "label_window_closed" in part.columns else pd.Series(False, index=part.index)
            rows.append(
                {
                    "frame_type": frame_name,
                    "horizon": horizon,
                    "cutoff_month": cutoff,
                    "row_count": len(part),
                    "closed_row_count": int(closed.sum()),
                    "open_row_count": int((~closed).sum()),
                    "max_observed_purchase_date": part.get("max_observed_purchase_date", pd.Series([pd.NaT])).iloc[0],
                    "label_window_end": part.get("label_window_end", pd.Series([pd.NaT])).max(),
                    "closed_rate": float(closed.mean()) if len(part) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def render_label_generation_audit(recurring_source: str, one_shot_source: str, recurring: pd.DataFrame, one_shot: pd.DataFrame) -> str:
    recurring_open = int((~recurring["label_window_closed"].astype(bool)).sum()) if not recurring.empty else 0
    one_shot_open = int((~one_shot["label_window_closed"].astype(bool)).sum()) if not one_shot.empty else 0
    return f"""# Label Generation Audit

1. Recurring label_die_H definition: label_die_H=1 when no valid purchase exists in (cutoff_month, cutoff_month + H]; label_alive_H=1 otherwise.
2. One-shot label_repeat_H definition: label_repeat_H=1 when cumulative purchase_count_asof_cutoff is at least 2 by first_purchase_month + H.
3. label_window_closed: true when label_window_end is within the observable label/feature horizon.
4. 2025 usage: no raw 2025 feature regeneration was performed. Recurring labels come from the existing alive_labels artifact; one-shot labels are bounded by existing feature snapshot max cutoff.
5. Recurring unclosed rows: {recurring_open}.
6. One-shot unclosed rows: {one_shot_open}.
7. Recurring label source: {recurring_source}.
8. One-shot label source: {one_shot_source}.
9. Full universe status: current prediction frames are candidate-level because no full-universe row-level probability prediction artifact was written by M1.
10. Utility backtest readiness: closed labels are now available where candidate-level predictions can be joined.
"""


def render_prediction_source_audit(recurring_source: str, one_shot_source: str) -> str:
    return f"""# Prediction Source Audit

- Recurring prediction source: M1 recurring_business_priority_candidates_by_horizon.csv.
- Recurring prediction scope: candidate-only, not full-universe.
- Recurring label source: {recurring_source}.
- One-shot prediction source: M2 one_shot_attention_candidates_enriched.csv.
- One-shot prediction scope: candidate-only one-shot attention list, not all first-purchase universe.
- One-shot label source: {one_shot_source}.
- Re-trained model: false.
- Tuned parameters: false.
- Saved model file: false.
- Probability candidate version: logistic_regression + frequency_decay_v1 + raw, as present in M1 report outputs.

Current frames are sufficient for candidate-level utility backtest. They are not a replacement for a full-universe prediction artifact.
"""


def render_summary(recurring: pd.DataFrame, one_shot: pd.DataFrame, recurring_source: str, one_shot_source: str) -> str:
    recurring_closed = int(recurring["label_window_closed"].astype(bool).sum()) if not recurring.empty else 0
    one_shot_closed = int(one_shot["label_window_closed"].astype(bool).sum()) if not one_shot.empty else 0
    recurring_rate = recurring_closed / len(recurring) if len(recurring) else 0.0
    one_shot_rate = one_shot_closed / len(one_shot) if len(one_shot) else 0.0
    ready = "yes" if recurring_closed > 0 and one_shot_closed > 0 else "partial" if recurring_closed > 0 or one_shot_closed > 0 else "no"
    return f"""# Row-Level Backtest Frame Summary

1. Recurring frame generated: {not recurring.empty}
2. Recurring frame rows: {len(recurring)}
3. Recurring closed label rows: {recurring_closed}
4. Recurring closed rate: {recurring_rate:.4f}
5. One-shot frame generated: {not one_shot.empty}
6. One-shot frame rows: {len(one_shot)}
7. One-shot closed label rows: {one_shot_closed}
8. One-shot closed rate: {one_shot_rate:.4f}
9. Recurring prediction source: candidate-only M1 candidate pool.
10. One-shot prediction source: candidate-only M2 enriched output.
11. Recurring label source: {recurring_source}
12. One-shot label source: {one_shot_source}
13. Full universe limitation: yes, prediction scope is candidate-only.
14. Can rerun utility_backtest_v1: {ready in ["yes", "partial"]}.
"""


def render_next_step(recurring: pd.DataFrame, one_shot: pd.DataFrame) -> str:
    recurring_closed = int(recurring["label_window_closed"].astype(bool).sum()) if not recurring.empty else 0
    one_shot_closed = int(one_shot["label_window_closed"].astype(bool).sum()) if not one_shot.empty else 0
    if recurring_closed > 0 and one_shot_closed > 0:
        ready = "yes"
        condition = "metrics are candidate-level, not full-universe."
    elif recurring_closed > 0 or one_shot_closed > 0:
        ready = "partial"
        condition = "one side has closed labels; missing side requires label closure or prediction-label join correction."
    else:
        ready = "no"
        condition = "label closure or prediction-label join must be corrected."
    return f"""# Row-Level Backtest Next Step

utility_backtest_ready = {ready}

condition = {condition}

Recommended next step:

1. Rerun alive_prediction_utility_backtest_v1 with these frames as row-level label inputs.
2. Interpret results as candidate-level utility metrics until a full-universe probability prediction artifact is materialized.
3. Do not treat one-shot repeat_probability_H as recurring churn_probability_H.
"""


def build_row_level_backtest_frames(root: Path, output_dir: Path, dry_run: bool = False) -> dict[str, pd.DataFrame]:
    if dry_run:
        inputs = _dry_run_inputs()
    else:
        reports = root / "reports"
        feature_root = root / "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12"
        inputs = {
            "candidate_by_horizon": read_csv_or_empty(
                reports / "alive_prediction_candidate_pool_v1/recurring_business_priority_candidates_by_horizon.csv"
            ),
            "one_shot_enriched": read_csv_or_empty(
                reports / "alive_prediction_one_shot_repeat_v1/one_shot_attention_candidates_enriched.csv"
            ),
            "status": read_csv_or_empty(reports / "alive_prediction_status_decision_v1/candidate_status_decision.csv"),
            "detector_v1": read_csv_or_empty(reports / "alive_prediction_detectors_v1/detector_evidence_results.csv"),
            "detector_v2": read_csv_or_empty(reports / "alive_prediction_detectors_v2/detector_evidence_results_v2.csv"),
            "alive_labels": read_parquet_or_empty(
                feature_root / "cutoff_2024-01_2024-12/alive_labels__H3_6_12.parquet"
            ),
            "feature_snapshots": read_parquet_or_empty(
                feature_root / "cutoff_2020-01_2024-12/feature_table__status0.parquet",
                columns=JOIN_ENTITY_COLS + ["cutoff_month", "purchase_count_asof_cutoff"],
            ),
        }

    recurring, recurring_source = build_recurring_backtest_frame(
        inputs["candidate_by_horizon"],
        inputs["alive_labels"],
        inputs["status"],
        inputs["detector_v1"],
        inputs["detector_v2"],
    )
    one_shot, one_shot_source = build_one_shot_repeat_backtest_frame(
        inputs["one_shot_enriched"], inputs["feature_snapshots"]
    )
    closure = label_closure_audit(recurring, one_shot)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "recurring_backtest_frame.csv", recurring, RECURRING_COLUMNS)
    write_csv(output_dir / "recurring_backtest_frame_sample.csv", recurring.head(100), RECURRING_COLUMNS)
    write_csv(output_dir / "one_shot_repeat_backtest_frame.csv", one_shot, ONE_SHOT_COLUMNS)
    write_csv(output_dir / "one_shot_repeat_backtest_frame_sample.csv", one_shot.head(100), ONE_SHOT_COLUMNS)
    write_csv(output_dir / "label_closure_audit.csv", closure)
    write_text(output_dir / "label_generation_audit.md", render_label_generation_audit(recurring_source, one_shot_source, recurring, one_shot))
    write_text(output_dir / "prediction_source_audit.md", render_prediction_source_audit(recurring_source, one_shot_source))
    write_text(output_dir / "row_level_backtest_frame_summary.md", render_summary(recurring, one_shot, recurring_source, one_shot_source))
    write_text(output_dir / "row_level_backtest_next_step.md", render_next_step(recurring, one_shot))

    return {"recurring": recurring, "one_shot": one_shot, "closure": closure}


def _dry_run_inputs() -> dict[str, pd.DataFrame]:
    candidate = pd.DataFrame(
        {
            "candidate_id": ["a|h1|d|drug_code|2024-01|3", "a|h2|d|drug_code|2024-01|3"],
            "manufacturer_code": ["a", "a"],
            "hospital_code": ["h1", "h2"],
            "drug_group": ["d", "d"],
            "drug_group_source": ["drug_code", "drug_code"],
            "cutoff_month": ["2024-01", "2024-01"],
            "horizon": [3, 3],
            "churn_probability_H": [0.8, 0.2],
            "relative_value_at_risk_H": [100.0, 50.0],
            "relative_business_priority_score_H": [80.0, 10.0],
            "probability_candidate_version": ["logistic_regression + frequency_decay_v1 + raw"] * 2,
            "demand_shape_label": ["smooth", "smooth"],
        }
    )
    labels = pd.DataFrame(
        {
            "manufacturer_code": ["a", "a"],
            "hospital_code": ["h1", "h2"],
            "drug_group": ["d", "d"],
            "cutoff_month": ["2024-01-31", "2024-01-31"],
            "label_alive_H3": [0, 1],
            "label_die_H3": [1, 0],
            "label_alive_H6": [0, 1],
            "label_die_H6": [1, 0],
            "label_alive_H12": [0, 1],
            "label_die_H12": [1, 0],
        }
    )
    one_shot = pd.DataFrame(
        {
            "manufacturer_code": ["a", "a"],
            "hospital_code": ["h1", "h2"],
            "drug_group": ["d", "d"],
            "drug_group_source": ["drug_code", "drug_code"],
            "first_purchase_month": ["2024-01", "2024-11"],
            "horizon": ["H3", "H3"],
            "repeat_probability_H": [0.7, 0.4],
            "one_shot_non_repeat_risk_H": [0.3, 0.6],
            "selected_attention_score": [10.0, 5.0],
            "selected_attention_policy": ["balanced_attention_score", "balanced_attention_score"],
            "probability_interpretation": ["first_purchase_repeat_probability_not_recurring_churn_probability"] * 2,
            "model_confidence": ["prototype_logistic", "prototype_logistic"],
        }
    )
    snapshots = pd.DataFrame(
        {
            "manufacturer_code": ["a", "a"],
            "hospital_code": ["h1", "h2"],
            "drug_group": ["d", "d"],
            "cutoff_month": ["2024-04-30", "2024-12-31"],
            "purchase_count_asof_cutoff": [2, 1],
        }
    )
    status = pd.DataFrame(
        {
            "candidate_type": ["recurring_business_priority"],
            "manufacturer_code": ["a"],
            "hospital_code": ["h1"],
            "drug_group": ["d"],
            "drug_group_source": ["drug_code"],
            "cutoff_month": ["2024-01"],
            "horizon": ["H3"],
            "final_candidate_status": ["priority_review"],
            "review_priority": ["P1"],
            "evidence_strength": ["medium"],
            "survival_state": ["likely_churn_interval"],
            "demand_shape_label": ["smooth"],
            "demand_shape_route": ["main_probability_model"],
        }
    )
    detector = pd.DataFrame(
        {
            "candidate_id": ["a|h1|d|drug_code|2024-01|3"],
            "detector_name": ["terminal_loss_warning"],
            "hit_flag": [True],
            "reason_code": ["interval_overdue"],
        }
    )
    return {
        "candidate_by_horizon": candidate,
        "alive_labels": labels,
        "one_shot_enriched": one_shot,
        "feature_snapshots": snapshots,
        "status": status,
        "detector_v1": detector,
        "detector_v2": pd.DataFrame(),
    }
