from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta


def iter_walk_forward_dates(start_date: date, end_date: date, step_days: int) -> Iterator[date]:
    current = start_date
    while current <= end_date:
        yield current
        current = current + timedelta(days=step_days)
