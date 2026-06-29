"""Business value weighted TopK metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from alg.metrics.ranking import ndcg_at_k, precision_at_k, resolve_k


def captured_value_at_k(y_true, score, value, k) -> float:
    y_true = np.asarray(y_true, dtype=float)
    score = np.asarray(score, dtype=float)
    value = np.asarray(value, dtype=float)
    kk = resolve_k(len(y_true), k)
    total_positive_value = float((y_true * value).sum())
    if total_positive_value == 0:
        return np.nan
    idx = np.argsort(-score)[:kk]
    return float((y_true[idx] * value[idx]).sum() / total_positive_value)


def expected_loss_captured_at_k(probability, score, value, k) -> float:
    probability = np.asarray(probability, dtype=float)
    score = np.asarray(score, dtype=float)
    value = np.asarray(value, dtype=float)
    expected_loss = probability * value
    total = float(expected_loss.sum())
    if total == 0:
        return np.nan
    idx = np.argsort(-score)[: resolve_k(len(probability), k)]
    return float(expected_loss[idx].sum() / total)


def cutoff_value_metrics(
    df: pd.DataFrame,
    label_col: str,
    probability_col: str,
    priority_col: str,
    value_col: str,
    k_values=(10, 20, 50, 100, "top_1_pct", "top_5_pct", "top_10_pct"),
    group_cols=("cutoff_month",),
) -> pd.DataFrame:
    rows: list[dict] = []
    for group_key, group in df.groupby(list(group_cols), dropna=False):
        if len(group_cols) == 1:
            group_key = (group_key,)
        key_dict = dict(zip(group_cols, group_key))
        for k in k_values:
            idx = np.argsort(-group[priority_col].to_numpy())[: resolve_k(len(group), k)]
            rows.append(
                {
                    **key_dict,
                    "k": k,
                    "captured_value_at_k": captured_value_at_k(group[label_col], group[priority_col], group[value_col], k),
                    "value_weighted_ndcg_at_k": ndcg_at_k(group[label_col], group[priority_col], k, gains=group[label_col] * group[value_col]),
                    "expected_loss_captured_at_k": expected_loss_captured_at_k(group[probability_col], group[priority_col], group[value_col], k),
                    "topk_total_value_at_risk": float(group[value_col].to_numpy()[idx].sum()),
                    "topk_average_business_priority_score": float(group[priority_col].to_numpy()[idx].mean()) if len(idx) else np.nan,
                    "precision_at_k_by_business_priority_guardrail": precision_at_k(group[label_col], group[priority_col], k),
                    "row_count": int(len(group)),
                }
            )
    return pd.DataFrame(rows)
