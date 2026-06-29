#!/usr/bin/env python
"""Generate temporal drift diagnostics for alive prediction evaluation.

This is an evaluation diagnostics patch, not a new model experiment. It reads
existing artifacts and writes aggregate reports only; it does not train models,
save model files, save prediction artifacts, refresh caches, or delete data.
"""

from __future__ import annotations

import argparse
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

import run_alive_prediction_small_model_experiments as small_models


KEY_COLS = ["manufacturer_code", "hospital_code", "drug_group"]
HORIZONS = [3, 6, 12]
METRIC_COLUMNS = [
    "precision_at_k",
    "recall_at_k",
    "ndcg_at_k",
    "lift_at_k",
    "captured_value_at_k",
    "value_weighted_ndcg_at_k",
    "brier_score",
    "log_loss",
    "ece",
    "auc",
    "pr_auc",
]
K_VALUES = ["10", "20", "50", "100", "top_1_pct", "top_5_pct", "top_10_pct"]
FOCUS_FEATURES = [
    "months_since_last_purchase_asof_cutoff",
    "months_since_first_purchase_asof_cutoff",
    "order_count_last_3m_asof_cutoff",
    "order_count_last_6m_asof_cutoff",
    "order_count_last_12m_asof_cutoff",
    "active_month_ratio_asof_cutoff",
    "months_observed_asof_cutoff",
    "adi_asof_cutoff",
    "value_at_risk_amount_nonnegative_H3_asof_cutoff",
    "value_at_risk_amount_nonnegative_H6_asof_cutoff",
    "value_at_risk_amount_nonnegative_H12_asof_cutoff",
]


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def dataframe_to_markdown(df: pd.DataFrame, *, index: bool = False) -> str:
    try:
        return df.to_markdown(index=index)
    except ImportError:
        return "```csv\n" + df.to_csv(index=index).rstrip() + "\n```"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def entity_count(df: pd.DataFrame) -> int:
    return int(df[KEY_COLS].drop_duplicates().shape[0]) if len(df) else 0


def load_feature_label_table(root: Path, args: argparse.Namespace, config: dict[str, Any]) -> pd.DataFrame:
    feature_path = root / args.feature_table
    labels_path = root / args.labels
    if not feature_path.exists():
        raise FileNotFoundError(f"Missing feature table: {feature_path}")
    if not labels_path.exists():
        raise FileNotFoundError(f"Missing labels table: {labels_path}")
    features = pd.read_parquet(feature_path)
    labels = pd.read_parquet(labels_path)
    rule_config = small_models.read_yaml(root / "configs/experiments/alive_prediction_rule_baseline.yaml")
    df = small_models.join_features_labels(features, labels)
    df = small_models.add_scope_flags(df, config, rule_config)
    df = small_models.add_missing_flags(df)
    df["cutoff_month"] = pd.to_datetime(df["cutoff_month"])
    df["cutoff_period"] = df["cutoff_month"].dt.to_period("M")
    return df


def build_cutoff_label_rate_trend(df: pd.DataFrame) -> pd.DataFrame:
    recurring = df[df["recurring_candidate_flag"]].copy()
    rows = []
    for period, group in recurring.groupby("cutoff_period", dropna=False):
        row = {
            "cutoff_month": str(period),
            "entity_count": entity_count(group),
        }
        for horizon in HORIZONS:
            col = f"label_die_H{horizon}"
            row[f"{col}_positive_rate"] = float(group[col].mean()) if col in group and len(group) else np.nan
            row[f"{col}_positive_count"] = int(group[col].sum()) if col in group and len(group) else 0
        rows.append(row)
    return pd.DataFrame(rows).sort_values("cutoff_month")


def build_cutoff_entity_count_trend(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for period, group in df.groupby("cutoff_period", dropna=False):
        all_seen = entity_count(group)
        monitorable = group[group.get("all_monitorable_flag", True).astype(bool)] if "all_monitorable_flag" in group else group
        recurring = group[group["recurring_candidate_flag"]]
        one_shot = group[group["one_shot_flag"]]
        rows.append(
            {
                "cutoff_month": str(period),
                "all_seen_entity_count": all_seen,
                "monitorable_entity_count": entity_count(monitorable),
                "recurring_entity_count": entity_count(recurring),
                "one_shot_entity_count": entity_count(one_shot),
                "recurring_rate": entity_count(recurring) / all_seen if all_seen else np.nan,
                "one_shot_rate": entity_count(one_shot) / all_seen if all_seen else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values("cutoff_month")


def add_unavailable_metric_columns(metrics: pd.DataFrame) -> pd.DataFrame:
    out = metrics.copy()
    for column in METRIC_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
    return out


def build_cutoff_metric_trend(root: Path, label_trend: pd.DataFrame) -> pd.DataFrame:
    path = root / "reports/alive_prediction_small_models/model_metrics_by_cutoff.csv"
    if not path.exists():
        return pd.DataFrame(columns=["model", "horizon", "scope", "cutoff_month", "k", *METRIC_COLUMNS])
    metrics = pd.read_csv(path)
    metrics = metrics[metrics["scope"] == "recurring_only"].copy()
    metrics["k"] = metrics["k"].astype(str)
    metrics = metrics[metrics["k"].isin(K_VALUES)].copy()
    metrics["cutoff_month"] = pd.to_datetime(metrics["cutoff_month"]).dt.to_period("M").astype(str)
    metrics = add_unavailable_metric_columns(metrics)
    label_long = []
    for _, row in label_trend.iterrows():
        for horizon in HORIZONS:
            label_long.append(
                {
                    "cutoff_month": row["cutoff_month"],
                    "horizon": horizon,
                    "positive_rate": row[f"label_die_H{horizon}_positive_rate"],
                    "entity_count": row["entity_count"],
                }
            )
    metrics = metrics.merge(pd.DataFrame(label_long), on=["cutoff_month", "horizon"], how="left")
    keep = ["model", "horizon", "scope", "cutoff_month", "k", *METRIC_COLUMNS, "positive_rate", "entity_count"]
    return metrics[[column for column in keep if column in metrics.columns]].sort_values(["model", "horizon", "cutoff_month", "k"])


def build_train_vs_test_metrics(df: pd.DataFrame, split: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_mask = (
        (df["cutoff_period"] >= pd.Period(split["train_cutoff_start"], freq="M"))
        & (df["cutoff_period"] <= pd.Period(split["train_cutoff_end"], freq="M"))
        & df["recurring_candidate_flag"]
    )
    if "one_shot_high_value_silence_flag" in df:
        train_mask = train_mask & (~df["one_shot_high_value_silence_flag"].astype(bool))
    test_mask = (
        (df["cutoff_period"] >= pd.Period(split["test_cutoff_start"], freq="M"))
        & (df["cutoff_period"] <= pd.Period(split["test_cutoff_end"], freq="M"))
        & df["recurring_candidate_flag"]
    )
    train = df[train_mask].copy()
    test = df[test_mask].copy()
    row = {
        "train_cutoff_start": split["train_cutoff_start"],
        "train_cutoff_end": split["train_cutoff_end"],
        "test_cutoff_start": split["test_cutoff_start"],
        "test_cutoff_end": split["test_cutoff_end"],
        "scope": "recurring_only",
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_entity_count": entity_count(train),
        "test_entity_count": entity_count(test),
        "train_cutoff_count": int(train["cutoff_period"].nunique()),
        "test_cutoff_count": int(test["cutoff_period"].nunique()),
    }
    for horizon in HORIZONS:
        col = f"label_die_H{horizon}"
        row[f"train_{col}_positive_rate"] = float(train[col].mean()) if len(train) else np.nan
        row[f"test_{col}_positive_rate"] = float(test[col].mean()) if len(test) else np.nan
    return pd.DataFrame([row]), build_feature_distribution_shift(df, train, test)


def build_feature_distribution_shift(df: pd.DataFrame, train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    config = small_models.read_yaml(project_root() / "configs/experiments/alive_prediction_small_models.yaml")
    numeric_cols, _categorical_cols, _missing = small_models.select_feature_columns(df, config, "catboost_small")
    rows = []
    for column in numeric_cols:
        if column not in train.columns or column not in test.columns:
            continue
        train_values = pd.to_numeric(train[column], errors="coerce")
        test_values = pd.to_numeric(test[column], errors="coerce")
        train_std = float(train_values.std())
        test_std = float(test_values.std())
        pooled_std = float(np.sqrt((train_std**2 + test_std**2) / 2)) if not np.isnan(train_std) and not np.isnan(test_std) else np.nan
        mean_diff = float(test_values.mean() - train_values.mean())
        rows.append(
            {
                "feature": column,
                "train_mean": float(train_values.mean()),
                "test_mean": float(test_values.mean()),
                "train_std": train_std,
                "test_std": test_std,
                "mean_diff": mean_diff,
                "pooled_std": pooled_std,
                "standardized_mean_diff": mean_diff / pooled_std if pooled_std and not np.isnan(pooled_std) else np.nan,
                "train_missing_rate": float(train_values.isna().mean()),
                "test_missing_rate": float(test_values.isna().mean()),
                "is_focus_feature": column in FOCUS_FEATURES,
            }
        )
    return pd.DataFrame(rows).sort_values("standardized_mean_diff", key=lambda s: s.abs(), ascending=False)


def period_name(cutoff_month: str) -> str:
    period = pd.Period(cutoff_month, freq="M")
    if pd.Period("2024-01", freq="M") <= period <= pd.Period("2024-04", freq="M"):
        return "early_2024"
    if pd.Period("2024-05", freq="M") <= period <= pd.Period("2024-08", freq="M"):
        return "mid_2024"
    if pd.Period("2024-09", freq="M") <= period <= pd.Period("2024-12", freq="M"):
        return "late_2024"
    return "outside_2024"


def aggregate_metric_rows(df: pd.DataFrame, aggregation_method: str, period: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    grouped = df.groupby(["model", "horizon", "scope", "k"], dropna=False)
    rows = []
    for keys, group in grouped:
        row = dict(zip(["model", "horizon", "scope", "k"], keys))
        row["aggregation_method"] = aggregation_method
        row["period"] = period
        for column in METRIC_COLUMNS:
            row[column] = float(group[column].mean()) if column in group else np.nan
        row["positive_rate"] = float(group["positive_rate"].mean()) if "positive_rate" in group else np.nan
        row["entity_count"] = float(group["entity_count"].mean()) if "entity_count" in group else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def build_drift_aware_metric_summary(root: Path, cutoff_trend: pd.DataFrame) -> pd.DataFrame:
    parts = []
    scope_path = root / "reports/alive_prediction_small_models/model_metrics_by_scope.csv"
    if scope_path.exists():
        raw = pd.read_csv(scope_path)
        raw = raw[(raw["scope"] == "recurring_only") & (raw["k"].astype(str).isin(K_VALUES))].copy()
        raw["k"] = raw["k"].astype(str)
        raw = add_unavailable_metric_columns(raw)
        raw["aggregation_method"] = "raw_overall"
        raw["period"] = "2024_overall"
        raw["entity_count"] = raw.get("row_count_y", raw.get("row_count", np.nan))
        parts.append(raw[["model", "horizon", "scope", "k", "aggregation_method", "period", *METRIC_COLUMNS, "positive_rate", "entity_count"]])
    parts.append(aggregate_metric_rows(cutoff_trend, "macro_by_cutoff", "2024_all_cutoffs_equal_weight"))
    if not cutoff_trend.empty:
        segmented = cutoff_trend.copy()
        segmented["period"] = segmented["cutoff_month"].map(period_name)
        for name in ["early_2024", "mid_2024", "late_2024"]:
            parts.append(aggregate_metric_rows(segmented[segmented["period"] == name], "early_mid_late_split", name))
    nonempty = [part for part in parts if part is not None and not part.empty]
    return pd.concat(nonempty, ignore_index=True) if nonempty else pd.DataFrame()


def write_guardrails(output_dir: Path) -> None:
    write_text(
        output_dir / "metric_interpretation_guardrails.md",
        "\n".join(
            [
                "# Metric Interpretation Guardrails",
                "",
                "本报告是评估诊断补丁，不是新模型实验结论。",
                "",
                "1. recurring_only 是主模型选择 scope。",
                "2. all_monitorable 只是覆盖面观察。",
                "3. one_shot_only 只是 diagnostic，不参与主模型选型。",
                "4. one_shot_high_value_attention_list 是 business-rule recall list，不是概率模型输出。",
                "5. 2024 late cutoffs 的高 Precision/NDCG 不能直接解释为模型更强。",
                "6. 如果 Precision/NDCG 高但 Lift 接近 1，说明主要来自 base rate 升高。",
                "7. 模型比较必须优先看 macro_by_cutoff、early/mid/late 分段指标、Lift、NDCG、ValueWeightedNDCG、ECE、LogLoss、Brier。",
                "8. 不得把 business_priority_score 解释为 probability。",
                "9. 不得跨 cutoff 混排计算 TopK。",
                "10. 后续 training_window_comparison 和 feature_ablation 必须复用这些 guardrails。",
            ]
        ),
    )


def write_diagnosis(
    output_dir: Path,
    label_trend: pd.DataFrame,
    entity_trend: pd.DataFrame,
    cutoff_trend: pd.DataFrame,
    train_vs_test: pd.DataFrame,
    feature_shift: pd.DataFrame,
    drift_summary: pd.DataFrame,
) -> None:
    row = train_vs_test.iloc[0]
    top_shift = feature_shift.head(20)
    late = label_trend[label_trend["cutoff_month"].between("2024-09", "2024-12")]
    early = label_trend[label_trend["cutoff_month"].between("2024-01", "2024-04")]
    h3_early = float(early["label_die_H3_positive_rate"].mean()) if not early.empty else np.nan
    h3_late = float(late["label_die_H3_positive_rate"].mean()) if not late.empty else np.nan
    top10 = cutoff_trend[cutoff_trend["k"].astype(str) == "top_10_pct"].copy()
    late_top10 = top10[top10["cutoff_month"].between("2024-09", "2024-12")]
    lines = [
        "# Temporal Drift Diagnosis",
        "",
        "本报告是评估诊断补丁，不是新模型实验结论。",
        "",
        "## Summary",
        "",
        f"- train_rows: {row['train_rows']}",
        f"- test_rows: {row['test_rows']}",
        f"- train_entity_count: {row['train_entity_count']}",
        f"- test_entity_count: {row['test_entity_count']}",
        f"- train_label_die_H3_positive_rate: {row['train_label_die_H3_positive_rate']:.6f}",
        f"- test_label_die_H3_positive_rate: {row['test_label_die_H3_positive_rate']:.6f}",
        f"- 2024 early H3 positive_rate mean: {h3_early:.6f}",
        f"- 2024 late H3 positive_rate mean: {h3_late:.6f}",
        "",
        "2024 recurring cohort is materially different from the 2022 train cohort: it is larger, generally more recently active, has more short-window orders, and has higher activity ratio/value-at-risk features.",
        "",
        "Current feature selection does not include cutoff_month, so the current evidence does not support saying the model directly depends on cutoff_month.",
        "",
        "The evidence does support that models are likely affected by recency/activity/cohort-age proxy variables. Confirm with feature importance, permutation importance, and feature group ablation before treating model-family differences as stable.",
        "",
        "## Top 20 Standardized Feature Mean Differences",
        dataframe_to_markdown(top_shift, index=False),
        "",
        "## Late-2024 Top 10 Percent Metrics",
        dataframe_to_markdown(late_top10[["model", "horizon", "cutoff_month", "precision_at_k", "ndcg_at_k", "lift_at_k", "positive_rate"]].head(60), index=False)
        if not late_top10.empty
        else "No late-2024 top_10_pct rows were available.",
        "",
        "## Artifact Limitation",
        "",
        "Existing model_metrics_by_cutoff.csv contains cutoff-level ranking metrics but not cutoff-level Brier/LogLoss/ECE/AUC/PR_AUC or value metrics. Those fields are preserved in drift-aware outputs and remain empty where the source artifact cannot support them.",
    ]
    write_text(output_dir / "temporal_drift_diagnosis.md", "\n".join(lines))
    write_text(
        output_dir / "train_vs_test_diagnostics.md",
        "\n".join(
            [
                "# Train vs Test Diagnostics",
                "",
                "本报告是评估诊断补丁，不是新模型实验结论。",
                "",
                "## Train/Test Scale And Label Rates",
                dataframe_to_markdown(train_vs_test, index=False),
                "",
                "## Feature Distribution Shift",
                "",
                "The 2024 recurring cohort is more recently active and higher-frequency than the 2022 train cohort based on the largest standardized mean differences.",
                "",
                dataframe_to_markdown(top_shift, index=False),
                "",
                "cutoff_month is not selected into X. The likely risk is indirect dependence through recency/activity/cohort-age proxies, not direct cutoff leakage.",
                "",
                "Feature importance, permutation importance, and feature group ablation are needed next to confirm which proxy families dominate.",
            ]
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate temporal drift diagnostics for alive prediction.")
    parser.add_argument("--config", default="configs/experiments/alive_prediction_small_models.yaml")
    parser.add_argument(
        "--feature-table",
        default="data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/cutoff_2022-01_2024-12/feature_table__status0.parquet",
    )
    parser.add_argument(
        "--labels",
        default="data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/cutoff_2022-01_2024-12/alive_labels__H3_6_12.parquet",
    )
    parser.add_argument("--output-dir", default="reports/alive_prediction_temporal_drift")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = project_root()
    config = small_models.read_yaml(root / args.config)
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    split = config["time_split"]
    df = load_feature_label_table(root, args, config)
    label_trend = build_cutoff_label_rate_trend(df)
    entity_trend = build_cutoff_entity_count_trend(df)
    cutoff_trend = build_cutoff_metric_trend(root, label_trend)
    train_vs_test, feature_shift = build_train_vs_test_metrics(df, split)
    drift_summary = build_drift_aware_metric_summary(root, cutoff_trend)

    label_trend.to_csv(output_dir / "cutoff_label_rate_trend.csv", index=False, encoding="utf-8-sig")
    entity_trend.to_csv(output_dir / "cutoff_entity_count_trend.csv", index=False, encoding="utf-8-sig")
    cutoff_trend.to_csv(output_dir / "cutoff_metric_trend_recurring_only.csv", index=False, encoding="utf-8-sig")
    train_vs_test.to_csv(output_dir / "train_vs_test_metrics.csv", index=False, encoding="utf-8-sig")
    feature_shift.to_csv(output_dir / "feature_distribution_shift.csv", index=False, encoding="utf-8-sig")
    drift_summary.to_csv(output_dir / "drift_aware_metric_summary.csv", index=False, encoding="utf-8-sig")
    write_guardrails(output_dir)
    write_diagnosis(output_dir, label_trend, entity_trend, cutoff_trend, train_vs_test, feature_shift, drift_summary)
    print({"output_dir": str(output_dir), "rows": {"label_trend": len(label_trend), "entity_trend": len(entity_trend), "cutoff_trend": len(cutoff_trend), "feature_shift": len(feature_shift), "drift_summary": len(drift_summary)}}, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
