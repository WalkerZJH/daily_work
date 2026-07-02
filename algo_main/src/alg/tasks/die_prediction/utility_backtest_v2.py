"""Candidate-level utility backtest v2 for alive prediction.

V2 consumes the row-level closed-window frames produced by
``row_level_backtest_frame.py``. It is explicitly candidate-level:
the recurring frame covers M1 candidates, not the full entity universe.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from alg.tasks.die_prediction.utility_backtest import (
    average_precision_score_simple,
    brier_score,
    expected_calibration_error,
    log_loss_score,
    ndcg_at_k,
    roc_auc_score_simple,
)


K_SPECS: list[int | str] = [10, 20, 50, 100, "top_5_pct", "top_10_pct"]
ONE_SHOT_K_SPECS: list[int | str] = [10, 20, 50, "top_5_pct", "top_10_pct"]


def read_csv_or_empty(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, **kwargs)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def write_csv(path: Path, df: pd.DataFrame, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    if columns is not None:
        for col in columns:
            if col not in out.columns:
                out[col] = np.nan
        out = out[columns]
    out.to_csv(path, index=False, encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def closed_rows(df: pd.DataFrame, label_col: str) -> pd.DataFrame:
    if df.empty or "label_window_closed" not in df.columns or label_col not in df.columns:
        return df.iloc[0:0].copy()
    out = df[df["label_window_closed"].astype(bool) & df[label_col].notna()].copy()
    out[label_col] = out[label_col].astype(int)
    return out


def _metric_dict(df: pd.DataFrame, label_col: str, score_col: str) -> dict[str, Any]:
    valid = df[[label_col, score_col]].dropna().copy()
    if valid.empty:
        return {
            "row_count": 0,
            "positive_rate": np.nan,
            "brier": np.nan,
            "logloss": np.nan,
            "ece": np.nan,
            "auc": np.nan,
            "pr_auc": np.nan,
        }
    y_true = valid[label_col].astype(int).to_numpy()
    y_score = np.clip(pd.to_numeric(valid[score_col], errors="coerce").to_numpy(dtype=float), 1e-9, 1 - 1e-9)
    keep = ~np.isnan(y_score)
    y_true = y_true[keep]
    y_score = y_score[keep]
    return {
        "row_count": int(len(y_true)),
        "positive_rate": float(np.mean(y_true)) if len(y_true) else np.nan,
        "brier": brier_score(y_true, y_score),
        "logloss": log_loss_score(y_true, y_score),
        "ece": expected_calibration_error(y_true, y_score),
        "auc": roc_auc_score_simple(y_true, y_score),
        "pr_auc": average_precision_score_simple(y_true, y_score),
    }


def _numeric_mean(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns:
        return np.nan
    values = df[col]
    if isinstance(values, pd.DataFrame):
        values = values.iloc[:, 0]
    return pd.to_numeric(values, errors="coerce").mean()


def _numeric_sum(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns:
        return 0.0
    values = df[col]
    if isinstance(values, pd.DataFrame):
        values = values.iloc[:, 0]
    return pd.to_numeric(values, errors="coerce").sum()


def candidate_probability_metrics(recurring_frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    closed = closed_rows(recurring_frame, "label_die_H")
    if closed.empty or "horizon" not in closed.columns:
        return pd.DataFrame(
            columns=[
                "horizon",
                "row_count",
                "positive_rate_die",
                "brier",
                "logloss",
                "ece",
                "auc",
                "pr_auc",
                "backtest_scope",
                "note",
            ]
        )
    for horizon, part in closed.groupby("horizon", dropna=False):
        metrics = _metric_dict(part, "label_die_H", "churn_probability_H")
        rows.append(
            {
                "horizon": horizon,
                "row_count": metrics["row_count"],
                "positive_rate_die": metrics["positive_rate"],
                "brier": metrics["brier"],
                "logloss": metrics["logloss"],
                "ece": metrics["ece"],
                "auc": metrics["auc"],
                "pr_auc": metrics["pr_auc"],
                "backtest_scope": "candidate_level",
                "note": "candidate-level M1 probability metrics; not full-universe recall",
            }
        )
    return pd.DataFrame(rows)


def calibration_bins(
    df: pd.DataFrame,
    *,
    label_col: str,
    score_col: str,
    observed_col: str,
    avg_col: str,
    n_bins: int = 10,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    closed = closed_rows(df, label_col)
    if closed.empty or "horizon" not in closed.columns:
        return pd.DataFrame()
    for horizon, part in closed.groupby("horizon", dropna=False):
        valid = part[[label_col, score_col]].dropna().copy()
        if valid.empty:
            continue
        valid[score_col] = pd.to_numeric(valid[score_col], errors="coerce")
        valid = valid[valid[score_col].notna()]
        valid["bin_id"] = pd.cut(
            valid[score_col], bins=np.linspace(0, 1, n_bins + 1), include_lowest=True, labels=False
        ) + 1
        out = (
            valid.groupby("bin_id", dropna=True)
            .agg(
                row_count=(label_col, "size"),
                **{
                    avg_col: (score_col, "mean"),
                    observed_col: (label_col, "mean"),
                    "min_pred": (score_col, "min"),
                    "max_pred": (score_col, "max"),
                },
            )
            .reset_index()
        )
        out["horizon"] = horizon
        rows.append(out)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _topk_n(k_spec: int | str, n: int) -> int:
    if isinstance(k_spec, int):
        return min(k_spec, n)
    pct = {"top_5_pct": 0.05, "top_10_pct": 0.10}[k_spec]
    return max(1, min(n, int(np.ceil(n * pct))))


def _policy_topk(part: pd.DataFrame, score_col: str, k_spec: int | str) -> pd.DataFrame:
    if score_col not in part.columns or part.empty:
        return part.iloc[0:0].copy()
    k = _topk_n(k_spec, len(part))
    return part.sort_values(score_col, ascending=False).head(k).copy()


def recurring_topk_metrics(recurring_frame: pd.DataFrame) -> pd.DataFrame:
    closed = closed_rows(recurring_frame, "label_die_H")
    if closed.empty or "horizon" not in closed.columns:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for horizon, part in closed.groupby("horizon", dropna=False):
        base_rate = part["label_die_H"].mean() if not part.empty else np.nan
        for k_spec in K_SPECS:
            for policy, score_col in [
                ("probability_topk", "churn_probability_H"),
                ("business_priority_topk", "relative_business_priority_score_H"),
            ]:
                selected = _policy_topk(part, score_col, k_spec)
                k = len(selected)
                labels_sorted = selected["label_die_H"].astype(int).to_numpy() if k else np.array([])
                precision = float(labels_sorted.mean()) if k else np.nan
                rows.append(
                    {
                        "horizon": horizon,
                        "row_count": len(part),
                        "K": k_spec,
                        "topk_policy": policy,
                        "topk_count": k,
                        "topk_die_count": int(labels_sorted.sum()) if k else 0,
                        "precision_at_k": precision,
                        "candidate_base_die_rate": base_rate,
                        "lift_vs_candidate_base": precision / base_rate if base_rate and not pd.isna(precision) else np.nan,
                        "avg_churn_probability_H": _numeric_mean(selected, "churn_probability_H"),
                        "avg_relative_value_at_risk_H": _numeric_mean(selected, "relative_value_at_risk_H"),
                        "avg_relative_business_priority_score_H": _numeric_mean(
                            selected, "relative_business_priority_score_H"
                        ),
                        "captured_relative_value": _numeric_sum(selected, "relative_value_at_risk_H"),
                        "ndcg_at_k": ndcg_at_k(labels_sorted, k),
                        "note": "business_priority_topk is resource allocation, not probability accuracy"
                        if policy == "business_priority_topk"
                        else "candidate-level probability topK",
                    }
                )
    return pd.DataFrame(rows)


def business_priority_candidate_light_check(recurring_frame: pd.DataFrame) -> pd.DataFrame:
    closed = closed_rows(recurring_frame, "label_die_H")
    if closed.empty or "horizon" not in closed.columns:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for horizon, part in closed.groupby("horizon", dropna=False):
        for k_spec in K_SPECS:
            prob = _policy_topk(part, "churn_probability_H", k_spec)
            bus = _policy_topk(part, "relative_business_priority_score_H", k_spec)
            prob_ids = set(prob.get("candidate_id", pd.Series(dtype=str)).astype(str))
            bus_ids = set(bus.get("candidate_id", pd.Series(dtype=str)).astype(str))
            rows.append(
                {
                    "horizon": horizon,
                    "K": k_spec,
                    "probability_topk_avg_probability": _numeric_mean(prob, "churn_probability_H"),
                    "business_topk_avg_probability": _numeric_mean(bus, "churn_probability_H"),
                    "probability_topk_avg_value": _numeric_mean(prob, "relative_value_at_risk_H"),
                    "business_topk_avg_value": _numeric_mean(bus, "relative_value_at_risk_H"),
                    "probability_topk_die_rate": prob["label_die_H"].mean() if not prob.empty else np.nan,
                    "business_topk_die_rate": bus["label_die_H"].mean() if not bus.empty else np.nan,
                    "overlap_count": len(prob_ids & bus_ids),
                    "overlap_rate": len(prob_ids & bus_ids) / max(1, len(bus_ids)),
                    "note": "business priority is a resource allocation check, not probability accuracy; manufacturer min-fill should be reviewed separately if low-probability entries dominate.",
                }
            )
    return pd.DataFrame(rows)


def one_shot_repeat_candidate_metrics(one_shot_frame: pd.DataFrame) -> pd.DataFrame:
    closed = closed_rows(one_shot_frame, "label_repeat_H")
    if closed.empty or "horizon" not in closed.columns:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for horizon, part in closed.groupby("horizon", dropna=False):
        repeat = _metric_dict(part, "label_repeat_H", "repeat_probability_H")
        non_repeat_part = part.copy()
        non_repeat_part["label_non_repeat_H"] = non_repeat_part["label_non_repeat_H"].astype(int)
        non_repeat = _metric_dict(non_repeat_part, "label_non_repeat_H", "one_shot_non_repeat_risk_H")
        rows.append(
            {
                "horizon": horizon,
                "row_count": repeat["row_count"],
                "repeat_positive_rate": repeat["positive_rate"],
                "non_repeat_rate": non_repeat["positive_rate"],
                "brier_repeat": repeat["brier"],
                "logloss_repeat": repeat["logloss"],
                "ece_repeat": repeat["ece"],
                "auc_repeat": repeat["auc"],
                "pr_auc_repeat": repeat["pr_auc"],
                "brier_non_repeat": non_repeat["brier"],
                "auc_non_repeat": non_repeat["auc"],
                "pr_auc_non_repeat": non_repeat["pr_auc"],
                "note": "one-shot repeat_probability_H is not recurring churn_probability_H",
            }
        )
    return pd.DataFrame(rows)


def one_shot_topk_metrics(one_shot_frame: pd.DataFrame) -> pd.DataFrame:
    closed = closed_rows(one_shot_frame, "label_repeat_H")
    if closed.empty or "horizon" not in closed.columns:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for horizon, part in closed.groupby("horizon", dropna=False):
        part = part.copy()
        part["label_non_repeat_H"] = part["label_non_repeat_H"].astype(int)
        for k_spec in ONE_SHOT_K_SPECS:
            for direction, score_col, label_col in [
                ("repeat_opportunity", "repeat_probability_H", "label_repeat_H"),
                ("non_repeat_risk", "one_shot_non_repeat_risk_H", "label_non_repeat_H"),
                ("selected_attention", "selected_attention_score", "label_repeat_H"),
            ]:
                selected = _policy_topk(part, score_col, k_spec)
                k = len(selected)
                labels = selected[label_col].astype(int).to_numpy() if k else np.array([])
                rows.append(
                    {
                        "horizon": horizon,
                        "K": k_spec,
                        "topk_direction": direction,
                        "topk_count": k,
                        "target_positive_count": int(labels.sum()) if k else 0,
                        "target_precision_at_k": float(labels.mean()) if k else np.nan,
                        "repeat_rate": selected["label_repeat_H"].mean() if k else np.nan,
                        "non_repeat_rate": selected["label_non_repeat_H"].mean() if k else np.nan,
                        "avg_repeat_probability_H": _numeric_mean(selected, "repeat_probability_H"),
                        "avg_one_shot_non_repeat_risk_H": _numeric_mean(
                            selected, "one_shot_non_repeat_risk_H"
                        ),
                        "avg_selected_attention_score": _numeric_mean(selected, "selected_attention_score"),
                        "note": "one-shot scores are first-purchase repeat/non-repeat attention signals, not recurring churn",
                    }
                )
    return pd.DataFrame(rows)


def _merge_recurring_on_keys(left: pd.DataFrame, right: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    if left.empty or right.empty:
        return left.copy()
    work = right.copy()
    if "horizon" in work.columns:
        work["horizon"] = work["horizon"].astype(str)
    if "cutoff_month" in work.columns:
        work["cutoff_month"] = work["cutoff_month"].astype(str)
    keys = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month", "horizon"]
    keep = [c for c in keys + cols if c in work.columns]
    work = work[keep].drop_duplicates(keys)
    out = left.copy()
    out["horizon"] = out["horizon"].astype(str)
    out["cutoff_month"] = out["cutoff_month"].astype(str)
    return out.merge(work, on=keys, how="left", suffixes=("", "_aux"))


def _normalize_horizon_series(series: pd.Series) -> pd.Series:
    text = series.astype(str)
    return np.where(text.str.upper().str.startswith("H"), text.str.upper(), "H" + text.str.replace(r"\.0$", "", regex=True))


def attach_detector_summary(recurring: pd.DataFrame, detector_v1: pd.DataFrame, detector_v2: pd.DataFrame) -> pd.DataFrame:
    if recurring.empty:
        return recurring.copy()
    frames = []
    for detector in [detector_v1, detector_v2]:
        if detector.empty:
            continue
        required = {"manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month", "horizon"}
        if not required.issubset(detector.columns):
            continue
        work = detector.copy()
        work = work[work.get("hit_flag", False).astype(bool)].copy()
        if work.empty:
            continue
        work["horizon"] = _normalize_horizon_series(work["horizon"])
        work["cutoff_month"] = work["cutoff_month"].astype(str)
        work["detector_summary_part"] = work["detector_name"].astype(str) + ":" + work.get("reason_code", "").fillna("").astype(str)
        frames.append(work)
    if not frames:
        return recurring.copy()
    evidence = pd.concat(frames, ignore_index=True)
    keys = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month", "horizon"]
    summary = (
        evidence.groupby(keys, dropna=False)["detector_summary_part"]
        .apply(lambda s: ";".join(s.astype(str).head(5)))
        .reset_index()
        .rename(columns={"detector_summary_part": "detector_summary_from_evidence"})
    )
    out = recurring.copy()
    out["horizon"] = _normalize_horizon_series(out["horizon"])
    out["cutoff_month"] = out["cutoff_month"].astype(str)
    out = out.merge(summary, on=keys, how="left")
    if "detector_hit_summary" in out.columns:
        out["detector_hit_summary"] = out["detector_hit_summary"].combine_first(out["detector_summary_from_evidence"])
    else:
        out["detector_hit_summary"] = out["detector_summary_from_evidence"]
    return out.drop(columns=["detector_summary_from_evidence"])


def survival_state_outcome_check(recurring_frame: pd.DataFrame, survival: pd.DataFrame) -> pd.DataFrame:
    closed = closed_rows(recurring_frame, "label_die_H")
    if closed.empty or "horizon" not in closed.columns:
        return pd.DataFrame()
    if not survival.empty:
        closed = _merge_recurring_on_keys(
            closed,
            survival,
            ["survival_state", "survival_confidence", "relative_business_priority_score_H", "churn_probability_H"],
        )
        for col in ["survival_state", "survival_confidence"]:
            aux = f"{col}_aux"
            if aux in closed.columns:
                closed[col] = closed[col].combine_first(closed[aux]) if col in closed.columns else closed[aux]
    rows = []
    for (horizon, state), part in closed.groupby(["horizon", "survival_state"], dropna=False):
        rows.append(
            {
                "horizon": horizon,
                "survival_state": state,
                "row_count": len(part),
                "observed_die_rate": part["label_die_H"].mean(),
                "avg_churn_probability_H": _numeric_mean(part, "churn_probability_H"),
                "avg_relative_business_priority_score_H": _numeric_mean(
                    part, "relative_business_priority_score_H"
                ),
                "avg_survival_confidence": _numeric_mean(part, "survival_confidence"),
                "note": "candidate-level survival association check, not survival model ablation",
            }
        )
    return pd.DataFrame(rows)


def detector_outcome_check(recurring_frame: pd.DataFrame, detector_v1: pd.DataFrame, detector_v2: pd.DataFrame) -> pd.DataFrame:
    closed = closed_rows(recurring_frame, "label_die_H")
    if closed.empty or "horizon" not in closed.columns:
        return pd.DataFrame()
    base = closed.groupby("horizon")["label_die_H"].mean().to_dict()
    frames = []
    for source, detector in [("v1", detector_v1), ("v2", detector_v2)]:
        if detector.empty:
            continue
        d = detector.copy()
        d["source"] = source
        frames.append(d)
    if not frames:
        return pd.DataFrame()
    evidence = pd.concat(frames, ignore_index=True)
    keys = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month", "horizon"]
    evidence = evidence.copy()
    closed = closed.copy()
    if "horizon" in evidence.columns:
        evidence["horizon"] = _normalize_horizon_series(evidence["horizon"])
    if "horizon" in closed.columns:
        closed["horizon"] = _normalize_horizon_series(closed["horizon"])
    if "cutoff_month" in evidence.columns:
        evidence["cutoff_month"] = evidence["cutoff_month"].astype(str)
    if "cutoff_month" in closed.columns:
        closed["cutoff_month"] = closed["cutoff_month"].astype(str)
    label_cols = keys + ["label_die_H", "churn_probability_H", "relative_business_priority_score_H"]
    join_keys = [c for c in keys if c in evidence.columns and c in closed.columns]
    if join_keys:
        joined = evidence.merge(
            closed[[c for c in label_cols if c in closed.columns]],
            on=join_keys,
            how="inner",
            suffixes=("_detector", ""),
        )
    else:
        joined = pd.DataFrame()
    if joined.empty and "candidate_id" in evidence.columns and "candidate_id" in closed.columns:
        joined = evidence.merge(
            closed[["candidate_id", "horizon", "label_die_H", "churn_probability_H", "relative_business_priority_score_H"]],
            on="candidate_id",
            how="inner",
            suffixes=("_detector", ""),
        )
        if "horizon_detector" in joined.columns:
            joined["horizon"] = joined["horizon"].combine_first(joined["horizon_detector"])
    if joined.empty:
        return pd.DataFrame()
    if "fdr_eligible" not in joined.columns:
        joined["fdr_eligible"] = False
    if "p_value" not in joined.columns:
        joined["p_value"] = np.nan
    if "severity" not in joined.columns:
        joined["severity"] = np.nan
    if "confidence" not in joined.columns:
        joined["confidence"] = np.nan
    rows = []
    for (horizon, name, hit), part in joined.groupby(["horizon", "detector_name", "hit_flag"], dropna=False):
        observed = part["label_die_H"].mean()
        candidate_base = base.get(horizon, np.nan)
        rows.append(
            {
                "horizon": horizon,
                "detector_name": name,
                "hit_flag": hit,
                "row_count": len(part),
                "observed_die_rate": observed,
                "candidate_base_die_rate": candidate_base,
                "lift_vs_candidate_base": observed / candidate_base if candidate_base else np.nan,
                "avg_severity": _numeric_mean(part, "severity"),
                "avg_confidence": _numeric_mean(part, "confidence"),
                "p_value_available_count": int(part["p_value"].notna().sum()),
                "fdr_eligible_count": int(part["fdr_eligible"].map(lambda x: bool(x) if pd.notna(x) else False).sum()),
                "fdr_status_note": "fdr_not_applied" if name == "purchase_frequency_decay_rate_test" else "",
                "note": "interface-only price/delivery evidence should not be interpreted as effective detector outcome",
            }
        )
    return pd.DataFrame(rows)


def status_outcome_check(recurring_frame: pd.DataFrame, status_decision: pd.DataFrame) -> pd.DataFrame:
    closed = closed_rows(recurring_frame, "label_die_H")
    if closed.empty or "horizon" not in closed.columns:
        return pd.DataFrame()
    if not status_decision.empty:
        closed = _merge_recurring_on_keys(
            closed, status_decision[status_decision.get("candidate_type") == "recurring_business_priority"].copy(), []
        )
    rows = []
    group_cols = ["horizon", "final_candidate_status", "review_priority", "evidence_strength"]
    for keys, part in closed.groupby(group_cols, dropna=False):
        horizon, final_status, priority, strength = keys
        rows.append(
            {
                "horizon": horizon,
                "final_candidate_status": final_status,
                "review_priority": priority,
                "evidence_strength": strength,
                "row_count": len(part),
                "observed_die_rate": part["label_die_H"].mean(),
                "avg_churn_probability_H": _numeric_mean(part, "churn_probability_H"),
                "avg_relative_business_priority_score_H": _numeric_mean(
                    part, "relative_business_priority_score_H"
                ),
                "note": "candidate-level recurring status outcome check; one-shot excluded from recurring die_H",
            }
        )
    return pd.DataFrame(rows)


def _mark_topk_flags(recurring: pd.DataFrame) -> pd.DataFrame:
    out = recurring.copy()
    out["in_probability_topk"] = False
    out["in_business_priority_topk"] = False
    if out.empty or "horizon" not in out.columns:
        return out
    for horizon, part in out.groupby("horizon", dropna=False):
        idx_prob = _policy_topk(part, "churn_probability_H", "top_10_pct").index
        idx_bus = _policy_topk(part, "relative_business_priority_score_H", "top_10_pct").index
        out.loc[idx_prob, "in_probability_topk"] = True
        out.loc[idx_bus, "in_business_priority_topk"] = True
    return out


def historical_true_positive_cases(recurring_frame: pd.DataFrame, max_total: int = 50, max_per_horizon: int = 20) -> pd.DataFrame:
    closed = _mark_topk_flags(closed_rows(recurring_frame, "label_die_H"))
    if closed.empty or "label_die_H" not in closed.columns:
        return _proof_case_columns()
    eligible_status = closed.get("final_candidate_status", pd.Series("", index=closed.index)).isin(["priority_review", "manual_review"])
    selected = closed[
        (closed["label_die_H"] == 1)
        & (eligible_status | closed["in_probability_topk"] | closed["in_business_priority_topk"])
    ].copy()
    if selected.empty:
        return _proof_case_columns()
    selected["_status_rank"] = selected.get("final_candidate_status", "").map({"priority_review": 0, "manual_review": 1}).fillna(2)
    selected = (
        selected.sort_values(["horizon", "_status_rank", "relative_business_priority_score_H"], ascending=[True, True, False])
        .groupby("horizon", group_keys=False)
        .head(max_per_horizon)
        .sort_values(["_status_rank", "relative_business_priority_score_H"], ascending=[True, False])
        .head(max_total)
        .copy()
    )
    selected["case_id"] = [f"candidate_tp_{i:03d}" for i in range(1, len(selected) + 1)]
    selected["prediction_source"] = np.where(
        selected.get("final_candidate_status", "").isin(["priority_review", "manual_review"]),
        selected.get("final_candidate_status", ""),
        np.where(selected["in_probability_topk"], "probability_topK", "business_priority_topK"),
    )
    selected["detector_summary"] = selected.get("detector_hit_summary", "")
    if "label_window_end" not in selected.columns:
        selected["label_window_end"] = np.nan
    selected["proof_case_note"] = "selected_true_positive_candidate_level_case_not_accuracy_report"
    cols = _proof_case_columns().columns.tolist()
    return selected[cols]


def _proof_case_columns() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "case_id",
            "manufacturer_code",
            "hospital_code",
            "drug_group",
            "cutoff_month",
            "horizon",
            "prediction_source",
            "churn_probability_H",
            "relative_business_priority_score_H",
            "final_candidate_status",
            "review_priority",
            "survival_state",
            "detector_summary",
            "label_die_H",
            "label_window_end",
            "proof_case_note",
        ]
    )


def candidate_false_positive_cases(recurring_frame: pd.DataFrame) -> pd.DataFrame:
    closed = _mark_topk_flags(closed_rows(recurring_frame, "label_die_H"))
    if closed.empty or "label_die_H" not in closed.columns:
        return _error_case_columns()
    eligible_status = closed.get("final_candidate_status", pd.Series("", index=closed.index)).isin(["priority_review", "manual_review"])
    selected = closed[
        (closed["label_die_H"] == 0)
        & (eligible_status | closed["in_probability_topk"] | closed["in_business_priority_topk"])
    ].copy()
    return _format_error_cases(selected, "candidate_false_positive")


def candidate_false_negative_like_cases(recurring_frame: pd.DataFrame) -> pd.DataFrame:
    closed = closed_rows(recurring_frame, "label_die_H")
    if closed.empty or "label_die_H" not in closed.columns:
        return _error_case_columns()
    eligible_status = closed.get("final_candidate_status", pd.Series("", index=closed.index)).isin(["priority_review", "manual_review"])
    selected = closed[(closed["label_die_H"] == 1) & (~eligible_status)].copy()
    return _format_error_cases(selected, "candidate_false_negative_like")


def _format_error_cases(selected: pd.DataFrame, case_type: str) -> pd.DataFrame:
    cols = [
        "case_type",
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "cutoff_month",
        "horizon",
        "churn_probability_H",
        "relative_business_priority_score_H",
        "final_candidate_status",
        "review_priority",
        "survival_state",
        "detector_summary",
        "label_die_H",
        "error_note",
    ]
    if selected.empty:
        return pd.DataFrame(columns=cols)
    out = selected.copy()
    out["case_type"] = case_type
    out["detector_summary"] = out.get("detector_hit_summary", "")
    out["error_note"] = (
        "candidate-level false-negative-like within M1 frame; not full-universe miss"
        if case_type == "candidate_false_negative_like"
        else "candidate-level false positive proxy outcome"
    )
    return out[cols]


def _error_case_columns() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "case_type",
            "manufacturer_code",
            "hospital_code",
            "drug_group",
            "cutoff_month",
            "horizon",
            "churn_probability_H",
            "relative_business_priority_score_H",
            "final_candidate_status",
            "review_priority",
            "survival_state",
            "detector_summary",
            "label_die_H",
            "error_note",
        ]
    )


def render_proof_case_cards(cases: pd.DataFrame) -> str:
    if cases.empty:
        return "# Candidate-Level Proof Case Cards\n\nNo selected true-positive candidate-level cases were generated.\n"
    blocks = ["# Candidate-Level Proof Case Cards", ""]
    for _, row in cases.iterrows():
        blocks.extend(
            [
                f"## {row['case_id']}",
                "",
                f"- Entity: {row['manufacturer_code']} / {row['hospital_code']} / {row['drug_group']}",
                f"- Cutoff and horizon: {row['cutoff_month']} / {row['horizon']}",
                f"- System signal at cutoff: source={row['prediction_source']}, status={row.get('final_candidate_status')}, priority={row.get('review_priority')}",
                f"- Risk and priority: churn_probability_H={row['churn_probability_H']}, relative_business_priority_score_H={row['relative_business_priority_score_H']}",
                f"- Evidence: survival_state={row.get('survival_state')}; detectors={row.get('detector_summary')}",
                f"- Future closed-window outcome: label_die_H={row['label_die_H']} through {row.get('label_window_end')}",
                "- This case shows historical candidate-level early-hit ability. It is not a complete accuracy report.",
                "",
            ]
        )
    return "\n".join(blocks)


def proof_case_disclaimer() -> str:
    return (
        "# Proof Case Disclaimer\n\n"
        "This file contains selected true-positive candidate-level historical cases only. It is not a complete accuracy report. "
        "Candidate-level false positives and false-negative-like cases are recorded separately. Full-universe recall is not available in this version.\n"
    )


def candidate_backtest_limitations() -> str:
    return """# Candidate Backtest Limitations

1. This is not a full-universe backtest.
2. The recurring frame comes from the M1 candidate table.
3. Full-universe recall cannot be computed.
4. The result cannot prove the system finds all future loss objects.
5. Proof cases are selected true-positive candidate-level cases only.
6. Business priority is not a probability model.
7. One-shot repeat probability is not recurring churn probability.
8. Detector severity and confidence are not probabilities.
9. A full entity x cutoff x horizon prediction + label frame is required for full-universe backtesting.
"""


def render_next_algorithm_action(
    m1: pd.DataFrame,
    m1_topk: pd.DataFrame,
    m2: pd.DataFrame,
    business: pd.DataFrame,
    survival: pd.DataFrame,
    detector: pd.DataFrame,
) -> str:
    lines = ["# Next Algorithm Action Decision", ""]
    m1_auc = pd.to_numeric(m1.get("auc", pd.Series(dtype=float)), errors="coerce").mean()
    m2_auc = pd.to_numeric(m2.get("auc_repeat", pd.Series(dtype=float)), errors="coerce").mean()
    best_prob = m1_topk[m1_topk.get("topk_policy", "") == "probability_topk"]["precision_at_k"].max() if not m1_topk.empty else np.nan
    best_bus = m1_topk[m1_topk.get("topk_policy", "") == "business_priority_topk"]["precision_at_k"].max() if not m1_topk.empty else np.nan
    lines.append(f"- M1 probability candidate-level AUC mean: {m1_auc:.3f}. Keep scorer if this is acceptable against candidate base rates.")
    lines.append(f"- M1 TopK max precision: probability_topK={best_prob:.3f}, business_priority_topK={best_bus:.3f}.")
    lines.append("- Business priority remains useful as resource allocation when it captures higher relative value; do not claim it is more probabilistically accurate.")
    lines.append(f"- M2 repeat candidate-level AUC mean: {m2_auc:.3f}. Keep or downgrade to group prior based on business tolerance for one-shot discrimination.")
    if not survival.empty:
        high = survival[survival["survival_state"].isin(["materially_overdue", "likely_churn_interval"])]["observed_die_rate"].mean()
        normal = survival[survival["survival_state"].eq("normal_interval")]["observed_die_rate"].mean()
        lines.append(f"- M3 survival check: overdue state die rate mean={high:.3f}, normal_interval die rate={normal:.3f}; review M3 if not separated.")
    if not detector.empty:
        d002 = detector[detector["detector_name"].eq("purchase_frequency_decay_rate_test")]
        if not d002.empty:
            hit = d002[d002["hit_flag"].astype(bool)]["observed_die_rate"].mean()
            non = d002[~d002["hit_flag"].astype(bool)]["observed_die_rate"].mean()
            lines.append(f"- D002 rate-test check: hit die rate={hit:.3f}, non-hit die rate={non:.3f}; pursue L3/FDR only if lift is meaningful.")
    lines.append("- Full-universe backtest is still required before making recall claims.")
    lines.append("- Candidate-level proof cases can support demos, but not complete accuracy claims.")
    lines.append("- Product display can proceed only with candidate-level limitation and no auto-dispatch language.")
    return "\n".join(lines) + "\n"


def render_summary(
    recurring: pd.DataFrame,
    one_shot: pd.DataFrame,
    m1: pd.DataFrame,
    m2: pd.DataFrame,
    business: pd.DataFrame,
    survival: pd.DataFrame,
    detector: pd.DataFrame,
    status: pd.DataFrame,
    proof: pd.DataFrame,
    fp: pd.DataFrame,
    fn_like: pd.DataFrame,
) -> str:
    rec_closed = len(closed_rows(recurring, "label_die_H"))
    one_closed = len(closed_rows(one_shot, "label_repeat_H"))
    m1_auc = pd.to_numeric(m1.get("auc", pd.Series(dtype=float)), errors="coerce").mean()
    m2_auc = pd.to_numeric(m2.get("auc_repeat", pd.Series(dtype=float)), errors="coerce").mean()
    return f"""# Candidate Utility Backtest Summary

1. Backtest scope: candidate-level.
2. Recurring closed label rows: {rec_closed}.
3. One-shot closed label rows: {one_closed}.
4. M1 probability metrics overview: mean candidate-level AUC={m1_auc:.3f}.
5. M2 repeat metrics overview: mean candidate-level repeat AUC={m2_auc:.3f}.
6. Business priority light check rows: {len(business)}; this is not probability accuracy.
7. Survival light check rows: {len(survival)}.
8. Detector light check rows: {len(detector)}.
9. Status light check rows: {len(status)}.
10. Proof case count: {len(proof)}.
11. Candidate false positive count: {len(fp)}.
12. Candidate false-negative-like count: {len(fn_like)}.
13. Current algorithm has candidate-level utility evidence: {rec_closed > 0 and one_closed > 0}.
14. Full-universe backtest still required: yes.

## Boundary

This report cannot compute full-universe recall or prove the system finds all future die_H=1 entities. The recurring frame
is limited to M1 candidates and one-shot is limited to M2 attention candidates.
"""


def _read_inputs(root: Path) -> dict[str, pd.DataFrame]:
    reports = root / "reports"
    frame_dir = reports / "alive_prediction_row_level_backtest_frame_v1"
    return {
        "recurring": read_csv_or_empty(frame_dir / "recurring_backtest_frame.csv"),
        "one_shot": read_csv_or_empty(frame_dir / "one_shot_repeat_backtest_frame.csv"),
        "survival": read_csv_or_empty(reports / "alive_prediction_survival_lite_v1/survival_refinement_results.csv"),
        "detector_v1": read_csv_or_empty(reports / "alive_prediction_detectors_v1/detector_evidence_results.csv"),
        "detector_v2": read_csv_or_empty(reports / "alive_prediction_detectors_v2/detector_evidence_results_v2.csv"),
        "status": read_csv_or_empty(reports / "alive_prediction_status_decision_v1/candidate_status_decision.csv"),
        "bundle": read_csv_or_empty(reports / "alive_prediction_evidence_bundle_v1/structured_evidence_bundle.csv"),
    }


def _dry_run_inputs() -> dict[str, pd.DataFrame]:
    recurring = pd.DataFrame(
        {
            "candidate_id": ["a", "b", "c", "d"],
            "manufacturer_code": ["m"] * 4,
            "hospital_code": ["h1", "h2", "h3", "h4"],
            "drug_group": ["d"] * 4,
            "drug_group_source": ["drug_code"] * 4,
            "cutoff_month": ["2024-01"] * 4,
            "horizon": ["H6"] * 4,
            "churn_probability_H": [0.9, 0.8, 0.2, 0.1],
            "relative_value_at_risk_H": [10, 5, 100, 80],
            "relative_business_priority_score_H": [9, 4, 20, 8],
            "label_die_H": [1, 1, 0, 0],
            "label_alive_H": [0, 0, 1, 1],
            "label_window_closed": [True] * 4,
            "final_candidate_status": ["priority_review", "manual_review", "observation_only", "low_confidence_watch"],
            "review_priority": ["P1", "P2", "P3", "P3"],
            "evidence_strength": ["medium", "weak", "insufficient", "insufficient"],
            "survival_state": ["likely_churn_interval", "materially_overdue", "normal_interval", "normal_interval"],
            "detector_hit_summary": ["terminal_loss_warning", "", "", ""],
        }
    )
    one_shot = pd.DataFrame(
        {
            "horizon": ["H3", "H3", "H3", "H3"],
            "repeat_probability_H": [0.8, 0.7, 0.2, 0.1],
            "one_shot_non_repeat_risk_H": [0.2, 0.3, 0.8, 0.9],
            "selected_attention_score": [10, 8, 7, 6],
            "label_repeat_H": [1, 1, 0, 0],
            "label_non_repeat_H": [0, 0, 1, 1],
            "label_window_closed": [True] * 4,
        }
    )
    detector = pd.DataFrame(
        {
            "candidate_id": ["a", "b"],
            "detector_name": ["terminal_loss_warning", "purchase_frequency_decay_rate_test"],
            "hit_flag": [True, True],
            "severity": [80, 50],
            "confidence": [0.7, 0.6],
            "p_value": [np.nan, 0.05],
            "fdr_eligible": [False, True],
        }
    )
    return {
        "recurring": recurring,
        "one_shot": one_shot,
        "survival": recurring[["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month", "horizon", "survival_state"]],
        "detector_v1": detector.iloc[[0]].copy(),
        "detector_v2": detector.iloc[[1]].copy(),
        "status": recurring.assign(candidate_type="recurring_business_priority"),
        "bundle": pd.DataFrame(),
    }


def run_candidate_utility_backtest_v2(root: Path, output_dir: Path, dry_run: bool = False) -> dict[str, pd.DataFrame]:
    inputs = _dry_run_inputs() if dry_run else _read_inputs(root)
    recurring = attach_detector_summary(inputs["recurring"], inputs["detector_v1"], inputs["detector_v2"])
    one_shot = inputs["one_shot"]

    m1_metrics = candidate_probability_metrics(recurring)
    m1_bins = calibration_bins(
        recurring,
        label_col="label_die_H",
        score_col="churn_probability_H",
        observed_col="observed_die_rate",
        avg_col="avg_predicted_churn_probability",
    )
    m1_topk = recurring_topk_metrics(recurring)
    business = business_priority_candidate_light_check(recurring)
    m2_metrics = one_shot_repeat_candidate_metrics(one_shot)
    m2_topk = one_shot_topk_metrics(one_shot)
    m2_bins = calibration_bins(
        one_shot,
        label_col="label_repeat_H",
        score_col="repeat_probability_H",
        observed_col="observed_repeat_rate",
        avg_col="avg_repeat_probability_H",
    )
    survival = survival_state_outcome_check(recurring, inputs["survival"])
    detector = detector_outcome_check(recurring, inputs["detector_v1"], inputs["detector_v2"])
    status = status_outcome_check(recurring, inputs["status"])
    proof = historical_true_positive_cases(recurring)
    fp = candidate_false_positive_cases(recurring)
    fn_like = candidate_false_negative_like_cases(recurring)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "recurring_candidate_probability_metrics.csv", m1_metrics)
    write_csv(output_dir / "recurring_candidate_topk_metrics.csv", m1_topk)
    write_csv(output_dir / "recurring_candidate_calibration_bins.csv", m1_bins)
    write_csv(output_dir / "business_priority_candidate_light_check.csv", business)
    write_csv(output_dir / "one_shot_repeat_candidate_metrics.csv", m2_metrics)
    write_csv(output_dir / "one_shot_repeat_topk_metrics.csv", m2_topk)
    write_csv(output_dir / "one_shot_repeat_calibration_bins.csv", m2_bins)
    write_csv(output_dir / "survival_state_outcome_check.csv", survival)
    write_csv(output_dir / "detector_outcome_check.csv", detector)
    write_csv(output_dir / "status_outcome_check.csv", status)
    write_csv(output_dir / "historical_true_positive_cases.csv", proof)
    write_csv(output_dir / "candidate_false_positive_cases.csv", fp)
    write_csv(output_dir / "candidate_false_negative_like_cases.csv", fn_like)

    write_text(output_dir / "proof_case_cards.md", render_proof_case_cards(proof))
    write_text(output_dir / "proof_case_disclaimer.md", proof_case_disclaimer())
    write_text(output_dir / "candidate_backtest_limitations.md", candidate_backtest_limitations())
    write_text(output_dir / "next_algorithm_action_decision.md", render_next_algorithm_action(m1_metrics, m1_topk, m2_metrics, business, survival, detector))
    write_text(
        output_dir / "candidate_utility_backtest_summary.md",
        render_summary(recurring, one_shot, m1_metrics, m2_metrics, business, survival, detector, status, proof, fp, fn_like),
    )

    return {
        "recurring": recurring,
        "one_shot": one_shot,
        "m1_metrics": m1_metrics,
        "m1_topk": m1_topk,
        "m2_metrics": m2_metrics,
        "m2_topk": m2_topk,
        "business": business,
        "survival": survival,
        "detector": detector,
        "status": status,
        "proof": proof,
        "false_positive": fp,
        "false_negative_like": fn_like,
    }
