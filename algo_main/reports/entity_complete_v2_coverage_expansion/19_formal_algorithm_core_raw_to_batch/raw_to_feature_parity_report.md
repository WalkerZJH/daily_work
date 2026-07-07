# Raw-To-Feature Parity Report

- blocked checks: 0
- warning checks: 4
- exact parity requirement: not fully passed unless blocked=0 and warning=0.

| metric                        | status   |   production_value |   reference_value | blocker_reason                                                                         |
|:------------------------------|:---------|-------------------:|------------------:|:---------------------------------------------------------------------------------------|
| row_count_match               | warn     |      194628        |            106647 | entity/cutoff universe differs between production runtime and exploration frame        |
| candidate_id_match_rate       | warn     |           0.547722 |                 1 |                                                                                        |
| required_feature_coverage     | pass     |          49        |                49 |                                                                                        |
| feature_order_match           | pass     |           1        |                 1 |                                                                                        |
| numeric_feature_mean_abs_diff | warn     |           2.36414  |                 0 | production feature engineering intentionally refactored; exact parity not yet achieved |
| categorical_match_rate        | warn     |           0.375343 |                 1 | categorical feature transformation differs                                             |
