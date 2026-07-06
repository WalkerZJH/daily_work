# Final Stage Decision

- internal_diagnostic_view: true
- analyst_view: true
- proof_case_report: true
- customer_facing_probability_service: false
- auto_dispatch: false

## Key Metrics

- selected model: xgboost_small
- XGBoost AUC / PR-AUC gain / ECE: 0.8183576387600482 / 0.30800456113935387 / 0.01908906591830002
- recommended M1 policy: multi_recall_union_top10
- M1 recall: 0.43433345731347417
- manual load: 8741.711111111112
- probability gate rows: 393377

Customer-facing probability service remains blocked because this is still a selected subset, probability availability must be enforced at runtime, and choice-set context is partial-platform only.
