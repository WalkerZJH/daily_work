"""Probability quality metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd


EPS = 1e-15


def brier_score(y_true, y_prob) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    return float(np.mean((y_prob - y_true) ** 2))


def log_loss(y_true, y_prob) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.clip(np.asarray(y_prob, dtype=float), EPS, 1 - EPS)
    return float(-(y_true * np.log(y_prob) + (1 - y_true) * np.log(1 - y_prob)).mean())


def auc_score(y_true, y_prob) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    positives = y_true == 1
    negatives = y_true == 0
    if positives.sum() == 0 or negatives.sum() == 0:
        return np.nan
    ranks = pd.Series(y_prob).rank(method="average").to_numpy()
    pos_rank_sum = ranks[positives].sum()
    return float((pos_rank_sum - positives.sum() * (positives.sum() + 1) / 2) / (positives.sum() * negatives.sum()))


def pr_auc_score(y_true, y_prob) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    if y_true.sum() == 0:
        return np.nan
    order = np.argsort(-y_prob)
    sorted_true = y_true[order]
    tp = np.cumsum(sorted_true)
    fp = np.cumsum(1 - sorted_true)
    precision = tp / np.maximum(tp + fp, EPS)
    recall = tp / y_true.sum()
    precision = np.r_[1.0, precision]
    recall = np.r_[0.0, recall]
    return float(np.trapezoid(precision, recall))


def calibration_curve(y_true, y_prob, n_bins: int = 10) -> pd.DataFrame:
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    bins = np.linspace(0, 1, n_bins + 1)
    ids = np.digitize(y_prob, bins[1:-1], right=True)
    rows = []
    for bin_id in range(n_bins):
        mask = ids == bin_id
        rows.append(
            {
                "bin": bin_id,
                "count": int(mask.sum()),
                "predicted_probability_mean": float(y_prob[mask].mean()) if mask.any() else np.nan,
                "actual_rate": float(y_true[mask].mean()) if mask.any() else np.nan,
            }
        )
    return pd.DataFrame(rows)


def expected_calibration_error(y_true, y_prob, n_bins: int = 10) -> float:
    curve = calibration_curve(y_true, y_prob, n_bins=n_bins)
    total = curve["count"].sum()
    if total == 0:
        return np.nan
    gaps = (curve["predicted_probability_mean"] - curve["actual_rate"]).abs().fillna(0)
    return float((gaps * curve["count"]).sum() / total)


def probability_metrics(y_true, y_prob) -> dict[str, float]:
    return {
        "brier_score": brier_score(y_true, y_prob),
        "log_loss": log_loss(y_true, y_prob),
        "ece": expected_calibration_error(y_true, y_prob),
        "auc": auc_score(y_true, y_prob),
        "pr_auc": pr_auc_score(y_true, y_prob),
    }
