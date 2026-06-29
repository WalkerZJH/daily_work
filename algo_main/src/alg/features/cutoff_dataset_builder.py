"""Candidate entity and cutoff dataset helpers."""

from __future__ import annotations

import pandas as pd

from alg.facts.purchase_event_builder import ENTITY_KEYS
from alg.utils.months import month_diff, to_month_end


def build_candidate_entities(
    purchase_events: pd.DataFrame,
    cutoff_months: list[pd.Timestamp] | None = None,
    policy: str = "monitorable",
    max_monitor_gap_months: int = 12,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build all_seen or monitorable candidates and cutoff count report."""

    if policy not in {"monitorable", "all_seen"}:
        raise ValueError("policy must be one of: monitorable, all_seen")
    events = purchase_events.copy()
    events["purchase_month"] = to_month_end(events["purchase_month"])
    if cutoff_months is None:
        cutoff_months = sorted(events["purchase_month"].dropna().unique())
    cutoff_months = [to_month_end(month) for month in cutoff_months]

    entity_bounds = (
        events.groupby(ENTITY_KEYS, dropna=False)["purchase_month"]
        .agg(first_purchase_month="min", last_purchase_month="max")
        .reset_index()
    )

    candidate_rows: list[dict] = []
    report_rows: list[dict] = []
    for cutoff in cutoff_months:
        seen = entity_bounds[entity_bounds["first_purchase_month"] <= cutoff].copy()
        if seen.empty:
            report_rows.append(
                {
                    "cutoff_month": cutoff,
                    "all_seen_entity_count": 0,
                    "monitorable_entity_count": 0,
                    "excluded_by_monitor_gap_count": 0,
                }
            )
            continue
        last_seen = (
            events[events["purchase_month"] <= cutoff]
            .groupby(ENTITY_KEYS, dropna=False)["purchase_month"]
            .max()
            .reset_index(name="last_purchase_month_asof_cutoff")
        )
        seen = seen.drop(columns=["last_purchase_month"]).merge(last_seen, on=ENTITY_KEYS, how="left")
        seen["months_since_last_purchase"] = seen["last_purchase_month_asof_cutoff"].apply(lambda value: month_diff(cutoff, value))
        monitorable = seen[seen["months_since_last_purchase"] <= max_monitor_gap_months].copy()
        selected = monitorable if policy == "monitorable" else seen
        for row in selected.to_dict("records"):
            row["cutoff_month"] = cutoff
            row["candidate_policy"] = policy
            candidate_rows.append(row)
        report_rows.append(
            {
                "cutoff_month": cutoff,
                "all_seen_entity_count": int(len(seen)),
                "monitorable_entity_count": int(len(monitorable)),
                "excluded_by_monitor_gap_count": int(len(seen) - len(monitorable)),
            }
        )
    return pd.DataFrame(candidate_rows), pd.DataFrame(report_rows)
