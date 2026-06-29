"""Sanity report builders for alive prediction."""

from __future__ import annotations

import pandas as pd


def build_entity_profile_report(candidate_report: pd.DataFrame, purchase_events: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Entity Profile Report",
            "",
            f"- purchase_time_min: {purchase_events['purchase_time'].min() if 'purchase_time' in purchase_events else None}",
            f"- purchase_time_max: {purchase_events['purchase_time'].max() if 'purchase_time' in purchase_events else None}",
            "",
            "## Candidate Counts By Cutoff",
            candidate_report.to_markdown(index=False) if not candidate_report.empty else "No candidate rows.",
        ]
    )


def build_label_distribution_report(labels: pd.DataFrame, horizons=(3, 6, 12)) -> str:
    lines = ["# Label Distribution Report", ""]
    for horizon in horizons:
        col = f"label_die_H{horizon}"
        if col in labels:
            lines.append(f"- {col}_positive_rate: {labels[col].mean()}")
    return "\n".join(lines)


def build_feature_null_report(features: pd.DataFrame) -> pd.DataFrame:
    row_count = max(len(features), 1)
    return pd.DataFrame(
        {
            "column": features.columns,
            "null_count": [int(features[column].isna().sum()) for column in features.columns],
            "null_rate": [float(features[column].isna().sum() / row_count) for column in features.columns],
            "dtype": [str(features[column].dtype) for column in features.columns],
        }
    )


def build_leakage_guardrail_report(
    feature_columns: list[str],
    include_status_history: bool,
) -> str:
    forbidden_prefixes = ("label_alive_H", "label_die_H", "next_purchase")
    forbidden_found = [column for column in feature_columns if column.startswith(forbidden_prefixes)]
    return "\n".join(
        [
            "# Leakage Guardrail Report",
            "",
            f"- status_history_features_enabled: {include_status_history}",
            f"- forbidden_label_or_future_columns_found: {forbidden_found}",
            "- feature_window_rule: purchase_month <= cutoff_month",
            "- label_window_rule: purchase_month in [cutoff_month + 1, cutoff_month + H]",
            "- value_at_risk_rule: prior history only",
        ]
    )
