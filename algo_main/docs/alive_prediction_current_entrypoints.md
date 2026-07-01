# Alive Prediction Current Entrypoints

## Notebook 展示入口

- `notebooks/02_alive_prediction_model_selection_story.ipynb`

## Notebook 生成入口

- `scripts/rebuild_alive_prediction_model_selection_notebook.py`

## 当前概率基线

- `logistic_regression + frequency_decay_v1 + raw`

## 当前业务可用结论

- `business_usable_probability_baseline = true`

## 当前报告入口

- `reports/alive_prediction_calibration_v2/`
- `reports/alive_prediction_feature_stability_v1/`
- `reports/alive_prediction_demand_shape_label_review/`
- `reports/alive_prediction_temporal_drift/`

## 历史报告入口

以下报告只列出，不删除；它们用于复核第二阶段决策链路。

- `reports/alive_prediction_small_models/`
- `reports/alive_prediction_small_models_expanded_train/`
- `reports/alive_prediction_feature_ablation/`
- `reports/alive_prediction_probability_consolidation/`
- `reports/alive_prediction_calibration_v1/`
- `reports/alive_prediction_calibration_review/`
- `reports/alive_prediction_rolling_origin_v1/`
- `reports/alive_prediction_probability_stabilization/`

## 脚本状态

| script | status | note |
| --- | --- | --- |
| `scripts/rebuild_alive_prediction_model_selection_notebook.py` | current | Rebuilds the second-stage model-selection story notebook. |
| `scripts/run_alive_prediction_demand_shape_label_review.py` | current | Demand-shape routing and label-policy review. |
| `scripts/run_alive_prediction_calibration_v2.py` | current | Current probability candidate decision. |
| `scripts/run_alive_prediction_feature_stability_v1.py` | current | Stable feature candidate evidence. |
| `scripts/run_alive_prediction_temporal_drift_diagnostics.py` | current | Cutoff-aware temporal drift guardrails. |
| `scripts/materialize_alive_prediction_artifacts.py` | utility | Reuse-first materialization utility; do not use for report-only notebook display. |
| `scripts/run_alive_prediction_calibration_v1.py` | historical | Historical calibration experiment. |
| `scripts/run_alive_prediction_calibration_review.py` | historical | Review layer for calibration v1. |
| `scripts/run_alive_prediction_rolling_origin_v1.py` | historical | Rolling-origin validation evidence. |
| `scripts/run_alive_prediction_probability_consolidation.py` | historical | Probability candidate consolidation evidence. |
| `scripts/run_alive_prediction_probability_stabilization.py` | historical | Stabilization diagnosis evidence. |
| `scripts/audit_alive_prediction_repo_cleanup.py` | utility | Dry-run cleanup audit; apply mode may only archive after explicit confirmation. |

## Guardrails

- Main model predicts only `churn_probability_H = P(die_H = 1)`.
- `recurring_only` is the primary model-selection scope.
- `one_shot_only` remains diagnostic only.
- `value_at_risk` and `business_priority_score` do not enter main probability model inputs or probability model selection.
- Do not delete data/cache/parquet/reports as part of cleanup audit.
