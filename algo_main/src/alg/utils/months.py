"""Month handling helpers for cutoff-based datasets."""

from __future__ import annotations

import pandas as pd


def to_month_end(value) -> pd.Series | pd.Timestamp:
    """Convert datetime-like values to month-end timestamps."""
    if isinstance(value, pd.Series):
        return pd.to_datetime(value, errors="coerce").dt.to_period("M").dt.to_timestamp("M")
    return pd.Timestamp(value).to_period("M").to_timestamp("M")


def add_months(month_end: pd.Timestamp, months: int) -> pd.Timestamp:
    """Add calendar months to a month-end timestamp and return month-end."""
    return (pd.Timestamp(month_end).to_period("M") + months).to_timestamp("M")


def month_diff(later: pd.Timestamp, earlier: pd.Timestamp) -> int:
    """Return whole month difference between two month-end timestamps."""
    later_period = pd.Timestamp(later).to_period("M")
    earlier_period = pd.Timestamp(earlier).to_period("M")
    return (later_period.year - earlier_period.year) * 12 + (later_period.month - earlier_period.month)


def month_range(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    """Inclusive month-end range."""
    periods = pd.period_range(pd.Timestamp(start).to_period("M"), pd.Timestamp(end).to_period("M"), freq="M")
    return [period.to_timestamp("M") for period in periods]
