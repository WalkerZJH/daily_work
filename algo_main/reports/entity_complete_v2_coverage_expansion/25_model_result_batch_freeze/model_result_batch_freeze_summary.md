# Model Result Batch Freeze Summary

## Scope

This freeze covers the model-side monthly result batch and daily detector result tables. It does not modify `project/` or `front_end/`.

## Batch

- Batch directory: `algo_main/data/entity_complete_v2_coverage_expansion/13_formal_algorithm_core_raw_to_batch/formal_result_batches/report_month=2025-12/batch_id=2025-12-monthly-risk-algorithm-formal-v2-raw`
- Report type: monthly
- Report month: 2025-12
- Primary horizon: H6
- Detector config version: `daily_detector_rules_v1`
- Readiness level: `conditional_fact_mode_ready`
- `raw_orders_mode_ready`: false
- `fact_mode_ready`: true
- `conditional_fact_mode_ready`: true

## Table Counts

| Table | Rows |
| --- | ---: |
| risk_entities | 1291 |
| monthly_reports | 1 |
| proof_cases | 0 |
| detector_catalog | 7 |
| daily_detector_runs | 1 |
| daily_detector_clues | 0 |
| high_risk_detector_evidence | 0 |

## Detector Semantics

- `detector_score` is not a probability.
- `detector_score` does not replace `monthly_risk_probability`.
- `detector_score` is only for rule-inspection clue ordering.
- Non-monthly-high-risk detector clues may exist in `daily_detector_clues`, but must not create `risk_entities`.
- `high_risk_detector_evidence` may only attach to existing `risk_entities`.
- Reserved, experimental, and interface-only detectors are disabled by default.

## Detector Catalog Status

- Implemented: `purchase_interval_ipi`, `purchase_quantity_trend`, `purchase_frequency_drop`
- Interface-only: `sku_shrink`
- Experimental: `fulfillment_gap`
- Reserved: `price_competition`, `peer_contrast`

## Deprecated Frontend Fields

The model-core dynamic payload no longer emits `fill_policy`. User scope, top-N, and any worklist shortage handling remain backend responsibilities.

The formal manifest records deprecated display-field guidance:

- `business_score`: not emitted by model-core customer payloads.
- `fill_policy`: removed from model-core payloads.

Downstream customer-facing display should use horizon profile amount/probability fields and should not expose internal strategy terms.

## Config Update Semantics

`configs/risk_algorithm_core/daily_detector_rules.yaml` now records:

- generated results are not rewritten by config changes;
- new config takes effect only after the next detector run;
- historical results keep their original `detector_config_version`;
- immediate reflection requires triggering a new detector run.

## Validation

Commands run:

```powershell
pytest -q tests/test_model_core_result_serving_boundary.py tests/test_final_model_result_batch_freeze.py
pytest -q tests/test_daily_detector_clues_allow_non_high_risk_but_do_not_create_risk_entities.py tests/test_daily_detector_catalog_marks_reserved_detectors.py tests/test_daily_detector_contract_utils.py tests/test_detector_capability_matrix_matches_design.py tests/test_ipi_detector_outputs_evidence_not_probability.py tests/test_frequency_drop_detector_schema.py tests/test_sku_shrink_detector_schema.py tests/test_high_risk_detector_evidence_only_attaches_existing_risk_entities.py tests/test_risk_model_core_reads_daily_detector_tables_without_raw_access.py tests/test_result_batch_contains_entity_display_lookup.py tests/test_model_core_result_serving_boundary.py tests/test_final_model_result_batch_freeze.py risk_model_core/tests/test_frontend_page_payloads.py
```

Results:

- Freeze tests: 8 passed.
- Detector/model-core regression subset: 20 passed.

