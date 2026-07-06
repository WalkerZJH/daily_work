# Next Data Action Decision

## Decision

Entity history is incomplete for enough sampled entities that model tuning should pause.

## Direct Answers

1. Current local data is suspected row-level SQL sample: yes, because notebook/pipeline use `SELECT TOP` with `sample_mode=True` / `max_rows=100000`.
2. Current local data is entity-history complete: no or not reliable; complete rate=0.0140.
3. Current model results may be polluted by sampling: likely.
4. Pause model tuning: yes.
5. Re-extract data: yes.
6. Recommended extraction: manufacturer_complete_then_entity_complete.
7. Continue full_universe_interval_backtest: No. Re-extract entity-complete or manufacturer-complete data before full_universe_interval_backtest is treated as reliable.
8. Fix data before algorithm: yes.

## Risk Flags

- top_n_or_ordered_sample_risk: high
- entity_history_incomplete_risk: high
- recent_period_overrepresented: false
- manufacturer_sampling_skew: true
- entity_age_sampling_skew: true
- interval_feature_distortion_risk: high
