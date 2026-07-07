# Risk Algorithm Core Extraction Summary

`risk_algorithm_core` has been added as the production-side monthly algorithm runtime layer.

Scope:

- input: raw business input batch, not feature batch;
- runtime: normalization, monthly entity construction, as-of feature engineering, artifact scoring, bounded candidate selection, detector gating, detector execution, status decision, RiskCard/Evidence assembly;
- output: monthly `risk_result_batch`;
- consumer: `risk_model_core`.

Safety:

- no import from `alg.*` or `algo_main.*`;
- no M closure source table dependency;
- no model training or tuning;
- no frontend or backend API implementation;
- `auto_dispatch_allowed=false`;
- `customer_facing_probability_service_allowed=false`.

Fixture run:

- report_month: `2026-07`;
- cutoff_date: `2026-07-31`;
- entity rows: 21;
- feature rows: 21;
- score rows: 21;
- selected candidate rows: 21;
- risk card rows: 69.
