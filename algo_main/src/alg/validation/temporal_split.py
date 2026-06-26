
"""Temporal split helpers for rolling cutoff validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TemporalWindow:
    """Feature and label windows for a single cutoff."""

    cutoff_date: date
    feature_end_date: date
    label_start_date: date
    label_end_date: date


def make_holdout_window(cutoff_date: date, horizon_months: int = 3, grace_months: int = 0) -> TemporalWindow:
    """Build a simple month-based holdout window.

    This scaffold uses 30-day months and should be replaced with calendar-aware
    logic when the label contract is finalized.
    """

    from datetime import timedelta

    label_start = cutoff_date + timedelta(days=grace_months * 30 + 1)
    label_end = cutoff_date + timedelta(days=(grace_months + horizon_months) * 30)
    return TemporalWindow(cutoff_date, cutoff_date, label_start, label_end)
