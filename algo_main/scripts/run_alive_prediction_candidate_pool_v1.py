#!/usr/bin/env python
"""Build M1 candidate-pool prototype outputs for alive prediction.

This script trains only temporary in-memory probability models to reproduce
the accepted Stage 1 scorer. It writes only prototype candidate/report outputs
under reports/alive_prediction_candidate_pool_v1/.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from alg.tasks.die_prediction.candidate_pool import (
    CandidatePoolConfig,
    build_demand_shape_observation_candidates,
    build_one_shot_attention_candidates,
    collapse_horizon_candidates,
    make_horizon_scored_frame,
    select_recurring_business_priority_candidates,
)

import run_alive_prediction_feature_stability_v1 as feature_stability
import run_alive_prediction_probability_consolidation as consolidation
import run_alive_prediction_small_model_experiments as small


OUTPUT_DIR = ROOT / "reports/alive_prediction_candidate_pool_v1"
MODEL = "logistic_regression"
FEATURE_SET = "frequency_decay_v1"
PROBABILITY_VERSION = "logistic_regression + frequency_decay_v1 + raw"
HORIZONS = [3, 6, 12]
TRAIN_START = "2020-01"
TRAIN_END = "2022-12"
SCORE_START = "2024-01"
SCORE_END = "2024-12"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def markdown_table(df: pd.DataFrame) -> str:
    return small.dataframe_to_markdown(df, index=False)


def cutoff_periods(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["cutoff_month"]).dt.to_period("M")


def cutoff_mask(df: pd.DataFrame, start: str, end: str) -> pd.Series:
    periods = cutoff_periods(df)
    return (periods >= pd.Period(start, freq="M")) & (periods <= pd.Period(end, freq="M"))


def normalize_cutoff_month(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["cutoff_month"] = pd.to_datetime(out["cutoff_month"]).dt.to_period("M").astype(str)
    return out


def load_feature_data(config: dict[str, Any]) -> pd.DataFrame:
    df = consolidation.load_feature_data(config)
    df = feature_stability.add_stability_features(df)
    df = normalize_cutoff_month(df)
    if "drug_group_source" not in df.columns:
        df["drug_group_source"] = "drug_code"
    return df


def split_train_score(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    periods = pd.PeriodIndex(df["cutoff_month"], freq="M")
    train = df[(periods >= pd.Period(TRAIN_START, freq="M")) & (periods <= pd.Period(TRAIN_END, freq="M"))].copy()
    train = train[train["recurring_candidate_flag"].astype(bool)].copy()
    if "one_shot_high_value_silence_flag" in train.columns:
        train = train[~train["one_shot_high_value_silence_flag"].astype(bool)].copy()
    score_all = df[(periods >= pd.Period(SCORE_START, freq="M")) & (periods <= pd.Period(SCORE_END, freq="M"))].copy()
    score_recurring = small.split_scopes(score_all)["recurring_only"].copy()
    return train, score_all, score_recurring


def selected_columns(config: dict[str, Any], train: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    spec = feature_stability.feature_sets()[FEATURE_SET]
    numeric, categorical, rejected = feature_stability.validate_features(train, spec["numeric"], spec["categorical"], config)
    if not numeric and not categorical:
        raise RuntimeError(f"no usable features for {FEATURE_SET}: {rejected}")
    return numeric, categorical, rejected


def score_probability_candidate(config: dict[str, Any], train: pd.DataFrame, score_recurring: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    numeric, categorical, rejected = selected_columns(config, train)
    long_frames: list[pd.DataFrame] = []
    failure_rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        label_col = f"label_die_H{horizon}"
        if label_col not in train.columns or label_col not in score_recurring.columns:
            failure_rows.append({"horizon": horizon, "reason": f"{label_col}_missing"})
            continue
        if train[label_col].isna().any() or score_recurring[label_col].isna().any():
            failure_rows.append({"horizon": horizon, "reason": f"{label_col}_has_missing"})
            continue
        if train[label_col].nunique(dropna=True) < 2:
            failure_rows.append({"horizon": horizon, "reason": f"{label_col}_single_class"})
            continue
        fitted, reason = feature_stability.expanded.fit_with_columns(MODEL, train, label_col, config, numeric, categorical, rejected)
        if fitted is None:
            failure_rows.append({"horizon": horizon, "reason": f"model_fit_failed:{reason}"})
            continue
        probability = small.predict_with_fitted_model(fitted, score_recurring)
        scored = make_horizon_scored_frame(
            score_recurring,
            horizon=horizon,
            probability=probability,
            probability_candidate_version=PROBABILITY_VERSION,
        )
        long_frames.append(scored)
    long_df = pd.concat(long_frames, ignore_index=True) if long_frames else pd.DataFrame()
    return long_df, pd.DataFrame(failure_rows, columns=["horizon", "reason"])


def one_shot_source(score_all: pd.DataFrame) -> pd.DataFrame | None:
    candidates = score_all.copy()
    if "one_shot_business_attention_flag" in candidates.columns:
        candidates = candidates[candidates["one_shot_business_attention_flag"].astype(bool)].copy()
    elif "one_shot_high_value_silence_flag" in candidates.columns:
        candidates = candidates[candidates["one_shot_high_value_silence_flag"].astype(bool)].copy()
    elif "one_shot_flag" in candidates.columns:
        candidates = candidates[candidates["one_shot_flag"].astype(bool)].copy()
    else:
        return None
    return candidates if not candidates.empty else None


def data_quality_report(
    score_long: pd.DataFrame,
    failures: pd.DataFrame,
    by_horizon: pd.DataFrame,
    entity_level: pd.DataFrame,
    one_shot: pd.DataFrame,
    observation: pd.DataFrame,
    audit: pd.DataFrame,
) -> str:
    rows = []
    if score_long.empty:
        rows.append("Stage 1 probability reproduction produced no scored recurring rows.")
    for horizon in HORIZONS:
        part = score_long[score_long["horizon"].eq(horizon)] if "horizon" in score_long.columns else score_long.iloc[0:0]
        if "relative_value_at_risk_H" in part.columns:
            missing = int(part["relative_value_at_risk_H"].isna().sum())
            rows.append(f"H{horizon} relative value missing rows: {missing}")
    if not failures.empty:
        rows.append("Probability reproduction failures:")
        rows.append(markdown_table(failures))
    else:
        rows.append("No probability reproduction failures.")
    rows.extend(
        [
            "",
            "## Output Row Counts",
            markdown_table(
                pd.DataFrame(
                    [
                        {"table": "score_long_in_memory_only", "row_count": len(score_long)},
                        {"table": "recurring_business_priority_candidates_by_horizon", "row_count": len(by_horizon)},
                        {"table": "recurring_business_priority_candidates", "row_count": len(entity_level)},
                        {"table": "one_shot_attention_candidates", "row_count": len(one_shot)},
                        {"table": "demand_shape_observation_candidates", "row_count": len(observation)},
                        {"table": "candidate_pool_selection_audit", "row_count": len(audit)},
                    ]
                )
            ),
            "",
            "All output files are prototype/report outputs. No model file or full row-level prediction artifact is saved.",
        ]
    )
    return "\n".join(["# Candidate Pool Data Quality Report", "", *rows])


def write_summary(
    by_horizon: pd.DataFrame,
    entity_level: pd.DataFrame,
    one_shot: pd.DataFrame,
    observation: pd.DataFrame,
    audit: pd.DataFrame,
    failures: pd.DataFrame,
) -> None:
    reason_summary = (
        by_horizon.groupby(["horizon", "selection_reason"], dropna=False)
        .size()
        .reset_index(name="candidate_count")
        if not by_horizon.empty
        else pd.DataFrame(columns=["horizon", "selection_reason", "candidate_count"])
    )
    lines = [
        "# Candidate Pool v1 Summary",
        "",
        "This is the M1 candidate pool prototype. It does not implement M2/M3/M4/M5/M6/M7 and does not train a new model.",
        "",
        "## Contract",
        "- Main high-priority candidates come only from `recurring_business_priority_candidates`.",
        "- Ranking uses `relative_business_priority_score_H = churn_probability_H * relative_value_at_risk_H`.",
        "- `relative_business_priority_score_H` is not a probability.",
        "- `relative_value_at_risk_H` is not a probability and is based on desensitized/relative amount fields.",
        "- one-shot and demand-shape observation tables are side tables and are not unioned into the main table.",
        "",
        "## Output Status",
        f"1. recurring_business_priority_candidates_by_horizon generated: {str(not by_horizon.empty).lower()} rows={len(by_horizon)}",
        f"2. recurring_business_priority_candidates generated: {str(not entity_level.empty).lower()} rows={len(entity_level)}",
        f"3. one_shot_attention_candidates generated: true rows={len(one_shot)}",
        f"4. demand_shape_observation_candidates generated: true rows={len(observation)}",
        "5. Main candidates are selected only by business-priority ranking.",
        "6. one-shot and demand-shape side tables are not merged into the main recurring table.",
        "7. business_priority_score is not interpreted as probability.",
        "8. one-shot rows do not receive recurring churn_probability.",
        "9. M2/M3/M4/M5/M6/M7 are not implemented in this run.",
        "10. No model file is saved.",
        "11. No data/cache/parquet/report deletion is performed.",
        "12. Next step can be M2 one-shot repeat propensity prototype or M3 survival-lite prototype.",
        "",
        "## Selection Reason Summary",
        markdown_table(reason_summary),
        "",
        "## Audit Summary",
        markdown_table(audit.groupby(["table_name", "selection_reason"], dropna=False)["selected_row_count"].sum().reset_index()) if not audit.empty else "No audit rows.",
        "",
        "## Probability Candidate",
        f"`{PROBABILITY_VERSION}`",
    ]
    if not failures.empty:
        lines.extend(["", "## Probability Reproduction Failures", markdown_table(failures)])
    write_text(OUTPUT_DIR / "candidate_pool_v1_summary.md", "\n".join(lines))


def run_candidate_pool() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = small.read_yaml(ROOT / "configs/experiments/alive_prediction_small_models.yaml")
    df = load_feature_data(config)
    train, score_all, score_recurring = split_train_score(df)
    score_long, failures = score_probability_candidate(config, train, score_recurring)
    pool_config = CandidatePoolConfig()
    by_horizon, audit_main = select_recurring_business_priority_candidates(score_long, config=pool_config)
    entity_level = collapse_horizon_candidates(by_horizon, config=pool_config)
    one_shot, audit_one_shot = build_one_shot_attention_candidates(one_shot_source(score_all))
    observation, audit_observation = build_demand_shape_observation_candidates(score_long)
    audit = pd.concat([audit_main, audit_one_shot, audit_observation], ignore_index=True)

    by_horizon.to_csv(OUTPUT_DIR / "recurring_business_priority_candidates_by_horizon.csv", index=False, encoding="utf-8-sig")
    entity_level.to_csv(OUTPUT_DIR / "recurring_business_priority_candidates.csv", index=False, encoding="utf-8-sig")
    one_shot.to_csv(OUTPUT_DIR / "one_shot_attention_candidates.csv", index=False, encoding="utf-8-sig")
    observation.to_csv(OUTPUT_DIR / "demand_shape_observation_candidates.csv", index=False, encoding="utf-8-sig")
    audit.to_csv(OUTPUT_DIR / "candidate_pool_selection_audit.csv", index=False, encoding="utf-8-sig")
    write_text(
        OUTPUT_DIR / "candidate_pool_data_quality_report.md",
        data_quality_report(score_long, failures, by_horizon, entity_level, one_shot, observation, audit),
    )
    write_summary(by_horizon, entity_level, one_shot, observation, audit, failures)


def main() -> int:
    run_candidate_pool()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
