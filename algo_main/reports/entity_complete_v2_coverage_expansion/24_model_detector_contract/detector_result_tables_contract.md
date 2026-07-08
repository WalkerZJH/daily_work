# Detector Result Tables Contract

## Batch Location

- local formal batch: `algo_main/data/entity_complete_v2_coverage_expansion/13_formal_algorithm_core_raw_to_batch/formal_result_batches/report_month=2025-12/batch_id=2025-12-monthly-risk-algorithm-formal-v2-raw`
- detector_catalog: `detector_catalog.csv` or `detector_catalog.parquet`
- daily_detector_runs: `daily_detector_runs.csv` or `daily_detector_runs.parquet`
- daily_detector_clues: `daily_detector_clues.csv` or `daily_detector_clues.parquet`
- high_risk_detector_evidence: `high_risk_detector_evidence.csv` or `high_risk_detector_evidence.parquet`

The local formal batch directory is ignored because it can contain generated business data. Future monthly runs write the same tables through `risk_algorithm_core.result_assembler`.

## Ownership

- `risk_algorithm_core` computes detector result tables.
- `risk_model_core` reads detector result tables only from `risk_result_batch` or equivalent result-serving tables.
- `project` should consume these tables through `risk_model_core`.
- `front_end` should consume detector fields only through backend API payloads.

## Semantic Guardrails

- `detector_score` is not a probability.
- `detector_score` does not replace `monthly_risk_probability`.
- `monthly_loss_value` comes from monthly risk result fields, not detector recomputation.
- `daily_detector_clues` may include non-monthly-high-risk clues.
- Non-monthly-high-risk clues must not create new `risk_entities`.
- `high_risk_detector_evidence` may attach only to existing `risk_entities`.
- Reserved/interface-only detectors are not enabled by default.
- Delivery responsibility, competitor replacement, policy loss, and definitive churn claims are forbidden.

## Implemented v1 Detectors

- `purchase_interval_ipi`
- `purchase_quantity_trend`
- `purchase_frequency_drop`

## Interface-only / Experimental / Reserved

- `sku_shrink`: interface only until product-line or portfolio mapping exists.
- `fulfillment_gap`: experimental; delivery and received time quality remains insufficient for default enablement.
- `price_competition`: reserved until comparable price and approval-number mapping are confirmed.
- `peer_contrast`: reserved until peer group quality is confirmed.
