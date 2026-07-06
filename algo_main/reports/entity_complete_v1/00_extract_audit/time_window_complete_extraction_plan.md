# Time-Window-Complete Extraction Plan

Phase A/B data volumes were intentionally bounded. A future time-window-complete run should first estimate rows for 2020-01 through 2026-06 by month and manufacturer, then request explicit confirmation before exporting all matching SQL detail.

Recommended next query is aggregate-only:

1. rows by month for 2020-01 through 2026-06;
2. entity count by month;
3. rows by manufacturer within the time window;
4. projected parquet size from Phase A/B compression ratio.
