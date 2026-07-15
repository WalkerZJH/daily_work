# Remaining Limitations

- Generated observation contexts cover four default dates plus the 2025-12-05 validation sample, not a full 90-day detector history.
- Full dataset scaling uses observed local batch timing. Set RISK_FULL_DATASET_ROW_COUNT to refine full ClickHouse row-count scaling.
- raw_orders_mode_ready remains false; current readiness remains conditional fact mode.
- No detector clues were fabricated for unavailable observation dates.
