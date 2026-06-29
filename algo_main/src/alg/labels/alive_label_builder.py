"""Build alive/die labels for cutoff windows."""

from __future__ import annotations

import pandas as pd

from alg.facts.purchase_event_builder import ENTITY_KEYS
from alg.utils.months import add_months, to_month_end


def build_alive_labels(
    purchase_events: pd.DataFrame,
    candidates: pd.DataFrame,
    horizons: tuple[int, ...] = (3, 6, 12),
) -> pd.DataFrame:
    """Attach alive/die labels using label months [cutoff + 1, cutoff + H]."""

    required_events = set(ENTITY_KEYS + ["purchase_month"])
    required_candidates = set(ENTITY_KEYS + ["cutoff_month"])
    missing_events = sorted(required_events.difference(purchase_events.columns))
    missing_candidates = sorted(required_candidates.difference(candidates.columns))
    if missing_events:
        raise ValueError(f"purchase_events is missing required columns: {missing_events}")
    if missing_candidates:
        raise ValueError(f"candidates is missing required columns: {missing_candidates}")

    events = purchase_events[ENTITY_KEYS + ["purchase_month"]].copy()
    events["purchase_month"] = to_month_end(events["purchase_month"])
    out = candidates.copy()
    out["cutoff_month"] = to_month_end(out["cutoff_month"])

    event_months = {
        tuple(row[key] for key in ENTITY_KEYS): set(group["purchase_month"])
        for row, group in events.groupby(ENTITY_KEYS, dropna=False)
        for row in [dict(zip(ENTITY_KEYS, row if isinstance(row, tuple) else (row,)))]
    }

    for horizon in horizons:
        alive_values = []
        for record in out.itertuples(index=False):
            key = tuple(getattr(record, key) for key in ENTITY_KEYS)
            cutoff = getattr(record, "cutoff_month")
            start = add_months(cutoff, 1)
            end = add_months(cutoff, horizon)
            months = event_months.get(key, set())
            alive = any(start <= month <= end for month in months)
            alive_values.append(int(alive))
        out[f"label_alive_H{horizon}"] = alive_values
        out[f"label_die_H{horizon}"] = [1 - value for value in alive_values]
    return out
