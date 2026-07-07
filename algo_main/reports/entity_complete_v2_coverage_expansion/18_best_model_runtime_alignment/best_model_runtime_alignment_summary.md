# Best Model Runtime Alignment Summary

1. Formal best model artifact found before export: false or stale; current artifact was reconstructed from frozen v2 configuration.
2. artifact_id: xgboost_small_without_choice_set_20260707043129
3. model_family: xgboost_small
4. feature_group: all_safe_features_without_choice_set
5. calibration: raw
6. excludes_choice_set: true
7. required_features: 49
8. production feature builder coverage: all required features are covered by runtime derivation or schema-declared defaults.
9. formal monthly runner artifact mode: enabled.
10. formal run missing artifact behavior: fail fast.
11. dry-run baseline: fixture/test only, not formal.
12. golden score parity status: pass
13. golden score max abs diff: 0.0
14. raw-to-feature parity: blocked, no matched raw input batch.
15. result batch parity: blocked until raw-to-feature parity exists.
16. current blocker: raw-to-feature exact parity requires a stable v2 raw input batch export.
