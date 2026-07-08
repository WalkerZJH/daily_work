# Source-Of-Truth Flow Map

## Purpose

This map freezes the source-of-truth chain that must guide `risk_algorithm_core` formalization. The current direction must not be "make warnings disappear by approximating the exploration flow." The correct direction is:

```text
verified exploration fact and feature flow
-> production-safe migration into risk_algorithm_core
-> raw source parity
-> raw-to-feature parity
-> model input parity
-> score parity
-> M1/M3/M4/M5/M7 result parity
-> risk_result_batch readability
```

## Authoritative Sources Found

### Facts And Features

Primary source file:

- `algo_main/src/alg/tasks/die_prediction/entity_complete_rebuild.py`

Important functions:

- `run_entity_complete_feature_build`
- `build_fact_purchase_event`
- `build_fact_entity_month`
- `build_entity_purchase_sequence`
- `build_monthly_feature_table_fast`
- `build_features_for_cutoff`
- `merge_latest_static_status`
- `merge_interval_demand`
- `merge_choice_context_for_cutoff`
- `finalize_feature_columns`
- `build_monthly_labels_fast`
- `build_model_frame`

Important outputs:

- `algo_main/data/entity_complete_v2_coverage_expansion/04_facts/fact_purchase_event.parquet`
- `algo_main/data/entity_complete_v2_coverage_expansion/04_facts/fact_entity_month.parquet`
- `algo_main/data/entity_complete_v2_coverage_expansion/04_facts/entity_purchase_sequence.parquet`
- `algo_main/data/entity_complete_v2_coverage_expansion/05_features/entity_cutoff_feature_table.parquet`
- `algo_main/data/entity_complete_v2_coverage_expansion/05_features/alive_labels_H3_H6_H12.parquet`

Interpretation:

- The verified exploration feature frame is generated from `model_base -> fact_purchase_event -> fact_entity_month -> cutoff features`.
- `risk_algorithm_core` must migrate the production-safe parts of this flow rather than maintain an unproven approximate feature builder.
- Choice-set features exist in the exploration feature table, but the best production artifact excludes choice-set from the main backbone.

### Best Model Artifact

Primary source file:

- `algo_main/scripts/export_best_model_artifact_to_algorithm_core.py`

Important functions:

- `load_v2_frame`
- `selected_xgb_config`
- `fit_per_horizon_artifact`
- `write_artifact_files`
- `write_golden_reference`

Important outputs:

- `model_artifacts/risk_algorithm_core/main_churn/current/artifact_manifest.json`
- `model_artifacts/risk_algorithm_core/main_churn/current/model.joblib`
- `model_artifacts/risk_algorithm_core/main_churn/current/feature_schema.json`
- `algo_main/data/entity_complete_v2_coverage_expansion/12_best_model_runtime_alignment/golden_reference/golden_model_feature_frame.parquet`
- `algo_main/data/entity_complete_v2_coverage_expansion/12_best_model_runtime_alignment/golden_reference/golden_score_frame.parquet`

Interpretation:

- Artifact score parity can be proven against `golden_model_feature_frame`.
- Artifact score parity does not prove raw-to-feature parity.
- The exporter itself remains an `algo_main` adapter and must not be imported by `risk_algorithm_core` runtime.

### Candidate Policy V2

Primary source file:

- `algo_main/src/alg/tasks/die_prediction/entity_complete_v2_coverage_expansion.py`

Important functions:

- `run_v2_candidate_policy`
- `select_recommended_candidate_rows`
- `select_multi_recall_union`
- `candidate_policy_by_manufacturer`
- `manufacturer_worklist_capacity`

Important outputs:

- `algo_main/reports/entity_complete_v2_coverage_expansion/07_candidate_policy_v2/candidate_policy_v2_metrics.csv`
- `algo_main/reports/entity_complete_v2_coverage_expansion/07_candidate_policy_v2/candidate_policy_v2_recommendation.md`
- `algo_main/data/entity_complete_v2_coverage_expansion/07_candidates/candidate_policy_v2_rows.parquet`

Interpretation:

- The verified v2 candidate strategy must be read from these artifacts and source functions.
- "Per user 20-50 rows" is a presentation/workload constraint, not a replacement for the core candidate policy.
- If per-user fill is needed, it belongs downstream of candidate selection and must preserve `selection_reason` and caveats.

### M Module Closure

Primary source file:

- `algo_main/src/alg/tasks/die_prediction/entity_complete_m_module_closure.py`

Important functions:

- `build_m1_closure`
- `build_manufacturer_worklist`
- `build_m3_survival_refinement`
- `build_m4_detector_evidence`
- `build_m5_status_decision`
- `build_m7_structured_evidence_bundle`

Important outputs:

- `algo_main/data/entity_complete_v2_coverage_expansion/09_m_module_closure/m1_recurring_business_priority_candidates_by_horizon.csv`
- `algo_main/data/entity_complete_v2_coverage_expansion/09_m_module_closure/m1_recurring_business_priority_candidates.csv`
- `algo_main/data/entity_complete_v2_coverage_expansion/09_m_module_closure/m1_one_shot_attention_candidates.csv`
- `algo_main/data/entity_complete_v2_coverage_expansion/09_m_module_closure/m1_demand_shape_observation_candidates.csv`
- `algo_main/data/entity_complete_v2_coverage_expansion/09_m_module_closure/m1_manufacturer_worklist_candidates.csv`
- `algo_main/data/entity_complete_v2_coverage_expansion/09_m_module_closure/m3_survival_refinement_results.csv`
- `algo_main/data/entity_complete_v2_coverage_expansion/09_m_module_closure/m4_detector_evidence_results.csv`
- `algo_main/data/entity_complete_v2_coverage_expansion/09_m_module_closure/m5_candidate_status_decision.csv`
- `algo_main/data/entity_complete_v2_coverage_expansion/09_m_module_closure/m7_structured_evidence_bundle.csv`

Interpretation:

- M1 recurring, one-shot, and demand-shape observation are separate outputs.
- M3 only refines recurring candidates.
- M4 evidence is not probability.
- M5 is a status organizer, not a new model.
- M7 is structured evidence, not an LLM line card.

## Correct Candidate / Worklist Separation

Core candidate policy must remain source-of-truth driven. It should not be silently replaced by "per user 20-50 rows."

The per-user requirement should be implemented as:

1. Start from verified M1 recurring candidates.
2. Allocate by user/owner only after org scope is available.
3. Fill shortages first from recurring lower-confidence candidates, then from observation or one-shot side channels.
4. Mark fill rows as `observation_only`, `low_confidence_watch`, or `one_shot_attention`.
5. Never mark fill rows as high risk only because a user needs 20-50 rows.
6. Report users with insufficient eligible candidates instead of fabricating high-risk output.

## Current Blocker

The source functions exist, but `risk_algorithm_core` has not yet proven that its runtime feature builder is a migrated equivalent of `entity_complete_rebuild.py`. Therefore:

- raw-to-feature parity remains the controlling blocker;
- full result-batch parity remains blocked until M1/M3/M4/M5/M7 logic is migrated or wrapped with proven equivalence;
- `formal_second_layer_ready=true` from the current modified reports should not be treated as final.

## Required Next Action

1. Do not commit the current adaptation patch.
2. Decide whether to rollback the high-risk runtime changes or isolate them behind diagnostics.
3. Migrate production-safe source functions from `entity_complete_rebuild.py` into `risk_algorithm_core`.
4. Add parity tests per migrated function.
5. Restore strict parity reporting instead of loosening result-batch checks.
6. Only after parity passes, rerun formal monthly batch and then reassess frontend readiness.

See `source_of_truth_flow_map.csv` for the row-level mapping.
