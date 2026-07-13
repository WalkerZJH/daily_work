# Golden Parity Report

## Artifact Score Parity

- status: warn
- matched rows: 1081902
- score_max_abs_diff: 0.28641141951084137
- score_mean_abs_diff: 0.019723753592301115
- score_corr: 0.994040111643014

## Raw-To-Feature Parity

- status: blocked
- blocker: No matched production raw input batch exists for exact v2 raw-to-feature parity; runtime feature coverage is audited in feature_parity_matrix.csv.

## Result Batch Parity

- status: blocked
- blocker: Full result-batch parity requires raw-to-feature parity first; artifact scorer parity is available.
