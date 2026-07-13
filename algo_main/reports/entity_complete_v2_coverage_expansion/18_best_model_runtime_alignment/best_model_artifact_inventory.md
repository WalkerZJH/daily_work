# Best Model Artifact Inventory

- source experiment: entity_complete_v2_coverage_expansion
- best model family: xgboost_small
- best feature group: all_safe_features_without_choice_set
- calibration: raw
- choice-set dependency: excluded from main backbone
- current production model artifact present: True
- selected exploration AUC: 0.8190319644940823
- selected exploration PR-AUC gain: 0.3080575268267463
- selected exploration ECE: 0.0180645446129345

| artifact_name                       | path                                                                                                           | exists   |       size_bytes | role                                 |
|:------------------------------------|:---------------------------------------------------------------------------------------------------------------|:---------|-----------------:|:-------------------------------------|
| model_family_comparison.csv         | algo_main\reports\entity_complete_v2_coverage_expansion\04_model_validation\model_family_comparison.csv        | True     |   9794           | exploration_report                   |
| feature_group_ablation_summary.csv  | algo_main\reports\entity_complete_v2_coverage_expansion\04_model_validation\feature_group_ablation_summary.csv | True     |   2388           | exploration_report                   |
| xgboost_sanity_grid.csv             | algo_main\reports\entity_complete_v2_coverage_expansion\04_model_validation\xgboost_sanity_grid.csv            | True     |   4287           | exploration_report                   |
| selected_model_predictions.parquet  | algo_main\data\entity_complete_v2_coverage_expansion\06_predictions\selected_model_predictions.parquet         | True     |      3.51512e+07 | golden_or_training_source            |
| entity_cutoff_feature_table.parquet | algo_main\data\entity_complete_v2_coverage_expansion\05_features\entity_cutoff_feature_table.parquet           | True     |      1.16262e+08 | golden_or_training_source            |
| alive_labels_H3_H6_H12.parquet      | algo_main\data\entity_complete_v2_coverage_expansion\05_features\alive_labels_H3_H6_H12.parquet                | True     |      4.43894e+06 | golden_or_training_source            |
| artifact_manifest.json              | model_artifacts\risk_algorithm_core\main_churn\current\artifact_manifest.json                                  | True     |   3327           | production_artifact_manifest         |
| model.joblib                        | model_artifacts\risk_algorithm_core\main_churn\current\model.joblib                                            | True     | 504921           | production_model_file                |
| feature_schema.json                 | model_artifacts\risk_algorithm_core\main_churn\current\feature_schema.json                                     | True     |  10859           | production_feature_schema            |
| best_model_family                   |                                                                                                                | True     |    nan           | xgboost_small                        |
| best_feature_group                  |                                                                                                                | True     |    nan           | all_safe_features_without_choice_set |
| calibration                         |                                                                                                                | True     |    nan           | raw                                  |
| choice_set_dependency               |                                                                                                                | True     |    nan           | excluded_from_main_backbone          |
