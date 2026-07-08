"""Purchase sequence helpers migrated from the exploration source flow."""

from __future__ import annotations

import pandas as pd

from .facts import ENTITY_KEYS


def build_entity_purchase_sequence(purchase_events: pd.DataFrame) -> pd.DataFrame:
    if purchase_events.empty:
        return pd.DataFrame()
    work = purchase_events.sort_values(ENTITY_KEYS + ["purchase_time", "order_detail_id"]).copy()
    work["sequence_index"] = work.groupby(ENTITY_KEYS, dropna=False).cumcount() + 1
    work["previous_purchase_time"] = work.groupby(ENTITY_KEYS, dropna=False)["purchase_time"].shift(1)
    work["gap_days_since_previous_purchase"] = (
        pd.to_datetime(work["purchase_time"]) - pd.to_datetime(work["previous_purchase_time"])
    ).dt.days
    return work
