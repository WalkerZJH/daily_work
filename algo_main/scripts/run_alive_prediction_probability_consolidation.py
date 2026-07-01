#!/usr/bin/env python
"""Consolidate churn probability candidates without saving model artifacts."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_alive_prediction_expanded_train_diagnostics as expanded
import run_alive_prediction_small_model_experiments as small


PRIMARY_SCOPE = "recurring_only"
OUTPUT_DIR = ROOT / "reports/alive_prediction_probability_consolidation"
TOP_PCTS = {"top_1_pct": 0.01, "top_5_pct": 0.05, "top_10_pct": 0.10}
PERIODS = {
    "early_2024": ("2024-01", "2024-04"),
    "mid_2024": ("2024-05", "2024-08"),
    "late_2024": ("2024-09", "2024-12"),
}

PROBABILITY_CANDIDATES = [
    ("logistic_regression", "base_recency_frequency_only"),
    ("xgboost_small", "base_recency_frequency_only"),
    ("xgboost_small", "base_plus_interval_features"),
    ("xgboost_small", "base_plus_demand_profile_features"),
    ("catboost_small", "base_recency_frequency_only"),
    ("catboost_small", "base_plus_interval_features"),
]

PROBABILITY_COLUMNS = [
    "model",
    "feature_set",
    "horizon",
    "scope",
    "aggregation_method",
    "period",
    "row_count",
    "entity_count",
    "positive_rate",
    "brier_score",
    "log_loss",
    "ece",
    "auc",
    "pr_auc",
    "precision_at_top_1_pct",
    "precision_at_top_5_pct",
    "precision_at_top_10_pct",
    "lift_at_top_1_pct",
    "lift_at_top_5_pct",
    "lift_at_top_10_pct",
    "ndcg_at_top_1_pct",
    "ndcg_at_top_5_pct",
    "ndcg_at_top_10_pct",
]

FORBIDDEN_FEATURE_PATTERNS = [
    "business_priority",
    "value_at_risk",
    "label_",
    "next_purchase",
    "future",
    "rank_by_",
    "captured_value",
    "expected_loss_captured",
    "cutoff_month",
]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def markdown_table(df: pd.DataFrame) -> str:
    return small.dataframe_to_markdown(df, index=False)


def period_mask(df: pd.DataFrame, start: str, end: str) -> pd.Series:
    periods = pd.to_datetime(df["cutoff_month"]).dt.to_period("M")
    return (periods >= pd.Period(start, freq="M")) & (periods <= pd.Period(end, freq="M"))


def entity_count(df: pd.DataFrame) -> int:
    return expanded.entity_count(df)


def ece_score(y_true: np.ndarray, y_score: np.ndarray, bins: int = 10) -> float:
    if len(y_true) == 0:
        return np.nan
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = len(y_true)
    ece = 0.0
    for lower, upper in zip(edges[:-1], edges[1:]):
        if upper == 1.0:
            mask = (y_score >= lower) & (y_score <= upper)
        else:
            mask = (y_score >= lower) & (y_score < upper)
        if not np.any(mask):
            continue
        ece += (mask.sum() / total) * abs(float(np.mean(y_true[mask])) - float(np.mean(y_score[mask])))
    return float(ece)


def ndcg_binary(y_true: np.ndarray, y_score: np.ndarray, top_n: int) -> float:
    if len(y_true) == 0 or top_n <= 0:
        return np.nan
    order = np.argsort(-y_score)[:top_n]
    gains = y_true[order].astype(float)
    discounts = 1.0 / np.log2(np.arange(2, len(gains) + 2))
    dcg = float(np.sum(gains * discounts))
    ideal_gains = np.sort(y_true.astype(float))[::-1][:top_n]
    idcg = float(np.sum(ideal_gains * discounts[: len(ideal_gains)]))
    return dcg / idcg if idcg > 0 else np.nan


def metric_row(
    df: pd.DataFrame,
    *,
    model: str,
    feature_set: str,
    horizon: int,
    aggregation_method: str,
    period: str,
    cutoff_month: str | None = None,
    compute_topk: bool = True,
) -> dict[str, Any]:
    label_col = f"label_die_H{horizon}"
    prob_col = f"churn_probability_H{horizon}"
    y = df[label_col].astype(float).to_numpy()
    p = np.clip(df[prob_col].astype(float).to_numpy(), 1e-15, 1 - 1e-15)
    row: dict[str, Any] = {
        "model": model,
        "feature_set": feature_set,
        "horizon": horizon,
        "scope": PRIMARY_SCOPE,
        "aggregation_method": aggregation_method,
        "period": period,
        "cutoff_month": cutoff_month,
        "row_count": int(len(df)),
        "entity_count": entity_count(df),
        "positive_rate": float(np.mean(y)) if len(y) else np.nan,
        "brier_score": float(np.mean((p - y) ** 2)) if len(y) else np.nan,
        "log_loss": float(log_loss(y, p, labels=[0, 1])) if len(y) else np.nan,
        "ece": ece_score(y, p),
        "auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else np.nan,
        "pr_auc": float(average_precision_score(y, p)) if len(np.unique(y)) == 2 else np.nan,
    }
    positives = float(np.sum(y))
    base_rate = row["positive_rate"]
    for name, pct in TOP_PCTS.items():
        if compute_topk:
            top_n = max(1, int(np.ceil(len(df) * pct))) if len(df) else 0
            order = np.argsort(-p)[:top_n]
            top_positive = float(np.sum(y[order])) if top_n else np.nan
            precision = top_positive / top_n if top_n else np.nan
            row[f"precision_at_{name}"] = precision
            row[f"lift_at_{name}"] = precision / base_rate if pd.notna(base_rate) and base_rate > 0 else np.nan
            row[f"ndcg_at_{name}"] = ndcg_binary(y, p, top_n)
            row[f"recall_at_{name}"] = top_positive / positives if positives > 0 and top_n else np.nan
        else:
            row[f"precision_at_{name}"] = np.nan
            row[f"lift_at_{name}"] = np.nan
            row[f"ndcg_at_{name}"] = np.nan
            row[f"recall_at_{name}"] = np.nan
    return row


def macro_from_cutoffs(cutoff_rows: pd.DataFrame, *, period: str, aggregation_method: str) -> dict[str, Any]:
    numeric_cols = [
        col
        for col in cutoff_rows.columns
        if col not in {"model", "feature_set", "horizon", "scope", "aggregation_method", "period", "cutoff_month"}
        and pd.api.types.is_numeric_dtype(cutoff_rows[col])
    ]
    first = cutoff_rows.iloc[0]
    row: dict[str, Any] = {
        "model": first["model"],
        "feature_set": first["feature_set"],
        "horizon": int(first["horizon"]),
        "scope": PRIMARY_SCOPE,
        "aggregation_method": aggregation_method,
        "period": period,
    }
    for col in numeric_cols:
        row[col] = float(cutoff_rows[col].mean()) if not cutoff_rows.empty else np.nan
    row["row_count"] = int(cutoff_rows["row_count"].sum()) if "row_count" in cutoff_rows else 0
    row["entity_count"] = float(cutoff_rows["entity_count"].mean()) if "entity_count" in cutoff_rows else np.nan
    return row


def score_candidate(
    config: dict[str, Any],
    ablation_config: dict[str, Any],
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    model: str,
    feature_set: str,
    horizon: int,
) -> pd.DataFrame:
    numeric_cols, categorical_cols, missing = expanded.ablation_feature_columns(test_df, config, ablation_config, model, feature_set)
    selected_cols = numeric_cols + categorical_cols
    forbidden = [
        column
        for column in selected_cols
        if any(pattern in column for pattern in FORBIDDEN_FEATURE_PATTERNS)
    ]
    if forbidden:
        raise RuntimeError(f"forbidden probability features selected: {forbidden}")
    fitted, reason = expanded.fit_with_columns(model, train_df, f"label_die_H{horizon}", config, numeric_cols, categorical_cols, missing)
    if fitted is None:
        raise RuntimeError(f"{model}/{feature_set}/H{horizon} failed: {reason}")
    return expanded.score_frame(fitted, test_df, horizon)


def probability_metrics_for_scored(scored: pd.DataFrame, model: str, feature_set: str, horizon: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    cutoff_rows: list[dict[str, Any]] = []
    for cutoff, part in scored.groupby(pd.to_datetime(scored["cutoff_month"]).dt.to_period("M"), sort=True):
        cutoff_rows.append(
            metric_row(
                part,
                model=model,
                feature_set=feature_set,
                horizon=horizon,
                aggregation_method="by_cutoff",
                period=str(cutoff),
                cutoff_month=str(cutoff),
            )
        )
    by_cutoff = pd.DataFrame(cutoff_rows)
    rows: list[dict[str, Any]] = [
        metric_row(
            scored,
            model=model,
            feature_set=feature_set,
            horizon=horizon,
            aggregation_method="raw_overall",
            period="all_2024",
            compute_topk=False,
        )
    ]
    rows.append(macro_from_cutoffs(by_cutoff, period="all_2024", aggregation_method="macro_by_cutoff"))
    for period, (start, end) in PERIODS.items():
        part_cutoffs = by_cutoff[by_cutoff["period"].between(start, end)]
        if not part_cutoffs.empty:
            rows.append(macro_from_cutoffs(part_cutoffs, period=period, aggregation_method="early_mid_late"))
    return pd.DataFrame(rows), by_cutoff


def load_feature_data(config: dict[str, Any]) -> pd.DataFrame:
    split = dict(config["time_splits"]["expanded_train_2020_2022"])
    include_status_history = bool(config["features"].get("status_history_features", {}).get("enabled", False))
    df = small.build_or_load_feature_label_table(config, split, refresh_cache=False, include_status_history=include_status_history)
    rule_config = small.read_yaml(ROOT / "configs/experiments/alive_prediction_rule_baseline.yaml")
    return small.add_scope_flags(df, config, rule_config)


def build_probability_reports() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = small.read_yaml(ROOT / "configs/experiments/alive_prediction_small_models.yaml")
    ablation_config = small.read_yaml(ROOT / "configs/experiments/alive_prediction_feature_ablation.yaml")
    split = dict(config["time_splits"]["expanded_train_2020_2022"])
    df = load_feature_data(config)
    train_df, test_all = expanded.split_train_test(df, split)
    test_df = small.split_scopes(test_all)[PRIMARY_SCOPE]
    metric_frames: list[pd.DataFrame] = []
    cutoff_frames: list[pd.DataFrame] = []
    failures: list[str] = []
    for model, feature_set in PROBABILITY_CANDIDATES:
        for horizon in config["horizons_months"]:
            try:
                scored = score_candidate(config, ablation_config, train_df, test_df, model, feature_set, int(horizon))
                metrics, by_cutoff = probability_metrics_for_scored(scored, model, feature_set, int(horizon))
                metric_frames.append(metrics)
                cutoff_frames.append(by_cutoff)
            except Exception as exc:
                failures.append(f"{model}/{feature_set}/H{horizon}: {exc}")
    metrics = pd.concat(metric_frames, ignore_index=True) if metric_frames else pd.DataFrame(columns=PROBABILITY_COLUMNS)
    by_cutoff = pd.concat(cutoff_frames, ignore_index=True) if cutoff_frames else pd.DataFrame()
    metrics[[col for col in PROBABILITY_COLUMNS if col in metrics.columns]].to_csv(
        OUTPUT_DIR / "probability_candidate_metrics.csv", index=False, encoding="utf-8-sig"
    )
    metrics[metrics["aggregation_method"].eq("macro_by_cutoff")].to_csv(
        OUTPUT_DIR / "probability_candidate_by_horizon.csv", index=False, encoding="utf-8-sig"
    )
    by_cutoff.to_csv(OUTPUT_DIR / "probability_candidate_by_cutoff.csv", index=False, encoding="utf-8-sig")
    metrics[metrics["aggregation_method"].eq("early_mid_late")].to_csv(
        OUTPUT_DIR / "probability_candidate_early_mid_late.csv", index=False, encoding="utf-8-sig"
    )
    write_decision_reports(metrics, by_cutoff, failures)


def shortlist_rows(metrics: pd.DataFrame) -> pd.DataFrame:
    macro = metrics[metrics["aggregation_method"].eq("macro_by_cutoff")].copy()
    ranking = candidate_ranking(macro)
    rows: list[dict[str, Any]] = []
    type_overrides = {
        ("logistic_regression", "base_recency_frequency_only"): "primary_probability_baseline",
        ("xgboost_small", "base_recency_frequency_only"): "nonlinear_probability_challenger",
        ("xgboost_small", "base_plus_interval_features"): "backup_probability_candidate",
        ("catboost_small", "base_recency_frequency_only"): "backup_probability_candidate",
        ("catboost_small", "base_plus_interval_features"): "holdout",
    }
    notes = {
        ("logistic_regression", "base_recency_frequency_only"): (
            "Current macro_by_cutoff probability metrics are best on the combined Brier/LogLoss/ECE/AUC/PR_AUC ordering; "
            "transparent, stable, and interpretable."
        ),
        ("xgboost_small", "base_recency_frequency_only"): (
            "XGBoost is not the current probability-metric winner; it is retained as a nonlinear challenger to test whether "
            "calibration can beat Logistic on validation-cutoff probability quality."
        ),
        ("xgboost_small", "base_plus_interval_features"): (
            "Interval features may contain signal, but current probability quality does not beat base-only."
        ),
        ("catboost_small", "base_recency_frequency_only"): (
            "Ranking signal is visible, but probability quality and calibration risk are weaker than Logistic."
        ),
        ("catboost_small", "base_plus_interval_features"): (
            "Hold out until interval features prove calibrated probability-quality gain."
        ),
    }
    weaknesses = {
        "primary_probability_baseline": "May underfit nonlinear churn behavior; use challenger comparison after calibration.",
        "nonlinear_probability_challenger": "H6/H12 probability quality is weaker than Logistic before calibration.",
        "backup_probability_candidate": "Not promoted unless validation calibration improves Brier/LogLoss/ECE.",
        "holdout": "Higher calibration and temporal-drift risk.",
    }
    for _, row in ranking.iterrows():
        key = (str(row["model"]), str(row["feature_set"]))
        if key not in type_overrides:
            continue
        candidate_type = type_overrides.get(key, "holdout")
        rows.append(
            {
                "candidate_type": candidate_type,
                "model": key[0],
                "feature_set": key[1],
                "horizon": "H3/H6/H12",
                "primary_probability_strength": (
                    f"rank={int(row['probability_rank'])}; macro_by_cutoff mean "
                    f"Brier={row['brier_score']:.4f}, LogLoss={row['log_loss']:.4f}, ECE={row['ece']:.4f}, "
                    f"AUC={row['auc']:.4f}, PR_AUC={row['pr_auc']:.4f}"
                ),
                "main_probability_weakness": weaknesses.get(candidate_type, "Needs validation calibration evidence."),
                "temporal_drift_risk": "medium; recency/activity/cohort-age proxy drift must be tracked by cutoff-aware metrics.",
                "calibration_need": "yes" if candidate_type != "primary_probability_baseline" else "moderate",
                "recommended_next_action": notes.get(key, "Keep as holdout; do not promote from TopK diagnostics."),
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_DIR / "probability_final_shortlist.csv", index=False, encoding="utf-8-sig")
    out.to_csv(OUTPUT_DIR / "probability_final_shortlist_v2.csv", index=False, encoding="utf-8-sig")
    return out


def candidate_ranking(macro: pd.DataFrame) -> pd.DataFrame:
    if macro.empty:
        return pd.DataFrame(
            columns=["model", "feature_set", "brier_score", "log_loss", "ece", "auc", "pr_auc", "probability_rank"]
        )
    grouped = (
        macro.groupby(["model", "feature_set"], dropna=False)[["brier_score", "log_loss", "ece", "auc", "pr_auc"]]
        .mean(numeric_only=True)
        .reset_index()
    )
    grouped = grouped.sort_values(
        ["brier_score", "log_loss", "ece", "auc", "pr_auc"],
        ascending=[True, True, True, False, False],
    ).reset_index(drop=True)
    grouped["probability_rank"] = np.arange(1, len(grouped) + 1)
    return grouped


def summarize_strength(df: pd.DataFrame) -> str:
    if df.empty:
        return "metrics_not_available"
    return (
        f"macro_by_cutoff mean Brier={df['brier_score'].mean():.4f}, "
        f"LogLoss={df['log_loss'].mean():.4f}, ECE={df['ece'].mean():.4f}, "
        f"AUC={df['auc'].mean():.4f}, PR_AUC={df['pr_auc'].mean():.4f}"
    )


def write_decision_reports(metrics: pd.DataFrame, by_cutoff: pd.DataFrame, failures: list[str]) -> None:
    shortlist = shortlist_rows(metrics)
    macro = metrics[metrics["aggregation_method"].eq("macro_by_cutoff")].copy()
    ranking = candidate_ranking(macro)
    early_late = metrics[metrics["aggregation_method"].eq("early_mid_late")].copy()
    feature_report = feature_group_report()
    write_text(OUTPUT_DIR / "probability_feature_group_decision_report.md", feature_report)
    write_text(OUTPUT_DIR / "calibration_feasibility_plan.md", calibration_plan())
    write_text(OUTPUT_DIR / "value_feature_exclusion_note.md", value_feature_note())
    write_text(OUTPUT_DIR / "probability_candidate_ranking_logic.md", ranking_logic_report(ranking))
    summary = [
        "# Probability Consolidation Summary",
        "",
        "本报告是概率候选模型收敛与校准可行性设计，不是业务排序模型结论。",
        "",
        "## Scope",
        "- Main target: churn_probability_H = P(die_H = 1), for H3/H6/H12.",
        "- Main selection scope: recurring_only.",
        "- all_monitorable remains coverage observation; one_shot_only remains diagnostic only.",
        "- No business_priority_score model, no value-weighted ranker, no uplift/survival/deep learning, no large tuning.",
        "- No formal model files or prediction artifacts are saved.",
        "",
        "## Probability Candidate Shortlist",
        markdown_table(shortlist),
        "",
        "## Macro By Cutoff Probability Metrics",
        markdown_table(macro.sort_values(["horizon", "brier_score"]).head(30)) if not macro.empty else "No metrics generated.",
        "",
        "## Early/Mid/Late Drift Check",
        markdown_table(early_late.sort_values(["horizon", "model", "feature_set", "period"]).head(60)) if not early_late.empty else "No period metrics generated.",
        "",
        "## Guardrails",
        "- Do not select probability models from raw overall Precision/NDCG alone.",
        "- raw_overall TopK fields are intentionally left blank because TopK must not be computed by cross-cutoff mixing.",
        "- If late-2024 Precision/NDCG is high but Lift is near 1, treat it as base-rate inflation, not stronger model skill.",
        "- cutoff_month is not in X; do not claim direct cutoff_month dependence.",
        "- Recency/activity/cohort-age proxy drift remains a key risk and must be tracked in calibration feasibility.",
        "- CapturedValue, ValueWeightedNDCG, ExpectedLossCaptured, value_at_risk totals, and business-priority guardrails are excluded from probability selection.",
        "",
        "## Failures",
        "\n".join(f"- {item}" for item in failures) if failures else "No candidate fit/evaluation failures.",
    ]
    write_text(OUTPUT_DIR / "probability_consolidation_summary.md", "\n".join(summary))
    summary_v2 = [
        "# Probability Consolidation Summary v2",
        "",
        "This report corrects the probability candidate ordering. It is not a business ranking model conclusion.",
        "",
        "## Corrected Candidate Relationship",
        "- Logistic Regression + base_recency_frequency_only is the current primary probability baseline because it is best on the macro_by_cutoff probability ordering.",
        "- XGBoost + base_recency_frequency_only is retained as a nonlinear probability challenger, not as the current probability-metric winner.",
        "- XGBoost + base_plus_interval_features is a backup candidate only; interval features need calibration evidence.",
        "- CatBoost candidates are backup/holdout because their raw ranking signal does not offset weaker probability quality and calibration risk.",
        "",
        "## Probability Ranking Logic",
        markdown_table(ranking),
        "",
        "## Final Shortlist v2",
        markdown_table(shortlist),
        "",
        "## Macro By Cutoff Probability Metrics",
        markdown_table(macro.sort_values(["horizon", "brier_score"]).head(30)) if not macro.empty else "No metrics generated.",
        "",
        "## Guardrails",
        "- Main target remains churn_probability_H = P(die_H = 1).",
        "- value_at_risk and business_priority_score do not enter the model and are not selection criteria.",
        "- Value-weighted metrics are excluded from probability model selection.",
        "- TopK Lift/NDCG/Precision are auxiliary churn-probability ranking diagnostics only.",
        "- raw_overall TopK is intentionally blank because TopK must not be computed by cross-cutoff mixing.",
        "- one_shot_only is diagnostic only and not part of main model selection.",
        "",
        "## Failures",
        "\n".join(f"- {item}" for item in failures) if failures else "No candidate fit/evaluation failures.",
    ]
    write_text(OUTPUT_DIR / "probability_consolidation_summary_v2.md", "\n".join(summary_v2))


def ranking_logic_report(ranking: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Probability Candidate Ranking Logic",
            "",
            "This report is about churn probability candidate selection only. It is not a business ranking model.",
            "",
            "## Ordering Rule",
            "Candidates are ranked from macro_by_cutoff metrics averaged across H3/H6/H12. The primary ordering is BrierScore, LogLoss, ECE, AUC, and PR_AUC, with lower Brier/LogLoss/ECE preferred and higher AUC/PR_AUC preferred. TopK Lift/NDCG/Precision are auxiliary diagnostics and do not drive the probability rank.",
            "",
            "## Current Probability Ranking",
            markdown_table(ranking) if not ranking.empty else "No ranking was generated.",
            "",
            "## Required Interpretations",
            "1. Logistic Regression cannot be just a sanity baseline because its macro_by_cutoff mean probability metrics are currently strongest overall; it is the primary probability baseline.",
            "2. XGBoost is retained as a challenger because it can represent nonlinear recency/frequency effects and may improve after validation-cutoff calibration, but it is not the current probability-metric winner.",
            "3. CatBoost is not the main probability candidate because the observed ranking signal comes with weaker probability quality and higher calibration risk.",
            "4. base_recency_frequency_only is probability_feature_set_v1 because it is direct, interpretable, low leakage risk, and strongest in probability-quality ablation.",
            "5. interval, demand profile, quantity history, and static features are held out because they have not shown a robust Brier/LogLoss/ECE improvement and can amplify temporal drift or cohort memorization.",
            "",
            "## probability_feature_set_v1",
            "- base_recency_frequency_only",
            "",
            "## Held-Out Feature Groups",
            "- interval_features",
            "- demand_profile_features",
            "- quantity_amount_history",
            "- static_category_features and high-cardinality identifiers",
            "- value_at_risk and business_priority related fields",
        ]
    )


def feature_group_report() -> str:
    path = ROOT / "reports/alive_prediction_feature_ablation/feature_ablation_metrics.csv"
    if not path.exists():
        return "# Probability Feature Group Decision Report\n\nFeature ablation metrics were not found."
    df = pd.read_csv(path)
    recurring = df[df["scope"].eq(PRIMARY_SCOPE)].copy()
    selected = recurring[recurring["ablation"].isin([
        "base_recency_frequency_only",
        "base_plus_interval_features",
        "base_plus_demand_profile_features",
        "base_plus_quantity_amount_history",
        "base_plus_static_category_features",
        "all_features",
        "all_features_without_value",
    ])]
    pivot = selected.groupby("ablation")[["brier_score", "log_loss", "ece", "auc", "pr_auc", "lift_at_top_10_pct", "ndcg_at_top_10_pct"]].mean().reset_index()
    return "\n".join(
        [
            "# Probability Feature Group Decision Report",
            "",
            "本报告是评估诊断补丁，不是新模型实验结论。",
            "",
            "## Ablation Probability Summary",
            markdown_table(pivot.sort_values(["brier_score", "log_loss"])),
            "",
            "## Answers",
            "1. base_recency_frequency_only is strong enough for the first probability v1 because it is directly interpretable and has the lowest leakage surface.",
            "2. interval_features are useful only if they improve Brier/LogLoss/ECE in calibration feasibility; they remain a backup add-on because interval missingness may proxy cohort maturity.",
            "3. demand_profile_features do not become the default unless they improve probability quality, not only ranking diagnostics.",
            "4. static high-cardinality category features are paused for the main probability v1 because they increase temporal drift and memorization risk.",
            "5. quantity_amount_history is held out until it proves probability-quality gain; historical amount/quantity statistics are not business_priority, but can still amplify cohort/value mix drift.",
            "6. all_features is not necessary for the probability mainline at this stage.",
            "7. value_at_risk and business_priority related fields are excluded from the main probability model.",
            "8. probability_feature_set_v1: base_recency_frequency_only.",
            "9. holdout_feature_sets: interval_features pending calibration proof; demand_profile_features; quantity_amount_history; static_category_features; value_at_risk/business_priority fields.",
            "",
            "## probability_feature_set_v1",
            "- base_recency_frequency_only",
            "",
            "## holdout_feature_sets",
            "- interval_features until validation calibration improves Brier/LogLoss/ECE",
            "- demand_profile_features",
            "- quantity_amount_history",
            "- static_category_features and other high-cardinality identifiers",
            "- value_at_risk and business_priority related fields",
        ]
    )


def calibration_plan() -> str:
    return """# Calibration Feasibility Plan

本报告是概率候选模型收敛与校准可行性设计，不是新模型实验结论。

## Rules
- Do not fit any calibrator on 2024 test.
- H3/H6/H12 must be calibrated separately.
- Keep raw probabilities: churn_probability_raw_H3, churn_probability_raw_H6, churn_probability_raw_H12.
- Output calibrated probabilities only in a future calibration experiment: churn_probability_calibrated_H3, churn_probability_calibrated_H6, churn_probability_calibrated_H12.

## Proposed Split
- model_train: 2020-01 ~ 2021-12
- calibration_valid: 2022-01 ~ 2022-12
- purge: 2023 is retained as the conservative H12 purge gap
- final_test: 2024-01 ~ 2024-12

## Methods To Compare
- Platt scaling
- isotonic regression

## Evaluation
- Brier before/after
- LogLoss before/after
- ECE before/after
- calibration bins before/after
- AUC/PR_AUC preservation
- TopK churn-probability ranking degradation check using Lift/NDCG/Precision, not value-weighted metrics

## Candidate Order
1. xgboost_small + base_recency_frequency_only
2. logistic_regression + base_recency_frequency_only as sanity baseline
3. xgboost_small + base_plus_interval_features as backup if probability quality improves
4. catboost_small + base_recency_frequency_only as backup
"""


def value_feature_note() -> str:
    return """# Value Feature Exclusion Note

本报告是概率候选模型收敛与校准可行性设计，不是业务排序模型结论。

1. The mainline model only predicts churn_probability_H = P(die_H = 1).
2. value_at_risk and business_priority_score do not enter the main probability model.
3. No business_priority model is being built in this stage.
4. Value-weighted metrics are not used for main probability model selection.
5. If the business later needs ranking, it must be an external post-processing layer: business_priority_score_H = churn_probability_H * value_at_risk_H.
6. That post-processing does not change the meaning of churn_probability_H.
7. This stage does not implement that post-processing.

## Field Boundary
- Historical purchase amount/quantity aggregates can be audited as ordinary history features.
- value_at_risk_amount_nonnegative_H*_asof_cutoff, value_at_risk_quantity_nonnegative_H*_asof_cutoff, business_priority_score_H*, one_shot_business_priority_score, rank_by_business_priority_H*, captured_value_at_k, expected_loss_captured, topk_total_value_at_risk, and topk_average_business_priority_score are excluded from probability candidate selection.
"""


def main() -> int:
    build_probability_reports()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
