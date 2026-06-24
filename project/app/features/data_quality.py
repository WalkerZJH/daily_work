from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd


def training_quality_summary(frame: pd.DataFrame) -> dict[str, Any]:
    warnings: Counter[str] = Counter()
    if frame.empty:
        warnings["EMPTY_TRAINING_DATASET"] += 1
        return {"warnings": dict(warnings), "row_count": 0}
    if "label_churn_H" in frame.columns:
        known = frame["label_churn_H"].dropna()
        if known.empty:
            warnings["NO_KNOWN_LABELS"] += 1
        elif known.nunique() < 2:
            warnings["SINGLE_CLASS_LABELS"] += 1
    missing_ratio = frame.isna().mean().sort_values(ascending=False)
    high_missing = missing_ratio[missing_ratio > 0.8]
    for column in high_missing.index:
        warnings[f"HIGH_MISSING_{column}"] += 1
    return {
        "warnings": dict(warnings),
        "row_count": int(len(frame)),
        "missing_ratio_top": {column: float(value) for column, value in missing_ratio.head(10).items()},
    }
