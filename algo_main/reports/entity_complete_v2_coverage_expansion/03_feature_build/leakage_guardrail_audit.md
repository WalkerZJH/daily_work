# Leakage Guardrail Audit

- Feature aggregations use `purchase_month <= cutoff_month`.
- Label windows use `(cutoff, cutoff + H]`.
- H3/H6/H12 closure flags are generated separately.
- 2026 data is used only to close earlier labels, never to construct features after a cutoff.
- ADI/CV2 and interval features are computed as-of cutoff through `entity_demand_profile_asof`.
- `median_purchase_interval_days_asof_cutoff` uses active-month gaps whose later month is no later than cutoff; it does not use future intervals.
- max observed purchase_time: 2026-06-24
