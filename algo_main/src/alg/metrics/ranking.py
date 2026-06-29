"""Cutoff-aware ranking metrics."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def resolve_k(group_size: int, k: int | float | str) -> int:
    if isinstance(k, str) and k.startswith("top_") and k.endswith("_pct"):
        pct = float(k.removeprefix("top_").removesuffix("_pct")) / 100
        return max(1, int(math.ceil(group_size * pct)))
    if isinstance(k, float) and 0 < k < 1:
        return max(1, int(math.ceil(group_size * k)))
    return max(1, min(int(k), group_size))


def precision_at_k(y_true, y_score, k: int | float | str) -> float:
    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)
    kk = resolve_k(len(y_true), k)
    if len(y_true) == 0:
        return np.nan
    idx = np.argsort(-y_score)[:kk]
    return float(y_true[idx].sum() / kk)


def recall_at_k(y_true, y_score, k: int | float | str) -> float:
    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)
    positives = y_true.sum()
    if positives == 0:
        return np.nan
    kk = resolve_k(len(y_true), k)
    idx = np.argsort(-y_score)[:kk]
    return float(y_true[idx].sum() / positives)


def ndcg_at_k(y_true, y_score, k: int | float | str, gains=None) -> float:
    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)
    gain_values = np.asarray(gains if gains is not None else y_true, dtype=float)
    kk = resolve_k(len(y_true), k)
    if kk == 0:
        return np.nan
    order = np.argsort(-y_score)[:kk]
    ideal = np.argsort(-gain_values)[:kk]
    discounts = 1 / np.log2(np.arange(2, kk + 2))
    dcg = float((gain_values[order] * discounts).sum())
    idcg = float((gain_values[ideal] * discounts).sum())
    return dcg / idcg if idcg else np.nan


def lift_at_k(y_true, y_score, k: int | float | str) -> float:
    base_rate = float(np.mean(y_true)) if len(y_true) else np.nan
    precision = precision_at_k(y_true, y_score, k)
    return precision / base_rate if base_rate else np.nan


def cutoff_topk_metrics(
    df: pd.DataFrame,
    label_col: str,
    score_col: str,
    k_values=(10, 20, 50, 100, "top_1_pct", "top_5_pct", "top_10_pct"),
    group_cols=("cutoff_month",),
) -> pd.DataFrame:
    """Compute TopK metrics inside each cutoff/group before aggregation."""

    rows: list[dict] = []
    for group_key, group in df.groupby(list(group_cols), dropna=False):
        for k in k_values:
            rows.append(
                {
                    **_group_key_dict(group_cols, group_key),
                    "k": k,
                    "precision_at_k": precision_at_k(group[label_col], group[score_col], k),
                    "recall_at_k": recall_at_k(group[label_col], group[score_col], k),
                    "ndcg_at_k": ndcg_at_k(group[label_col], group[score_col], k),
                    "lift_at_k": lift_at_k(group[label_col], group[score_col], k),
                    "row_count": int(len(group)),
                }
            )
    return pd.DataFrame(rows)


def _group_key_dict(group_cols, group_key) -> dict:
    if len(group_cols) == 1:
        group_key = (group_key,)
    return dict(zip(group_cols, group_key))
