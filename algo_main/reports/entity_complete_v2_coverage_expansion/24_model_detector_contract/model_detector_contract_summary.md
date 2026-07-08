# Model Detector Contract

## Boundary

- risk_algorithm_core calculates detector result tables from result-batch/monthly run inputs.
- risk_model_core only reads detector result tables from risk_result_batch or equivalent result-serving tables.
- project and front_end are not modified by this model-side contract step.
- detector_score is a rule evidence score, not a probability, and does not replace monthly_risk_probability.
- daily_detector_clues may include non-monthly-high-risk clues, but they do not create risk_entities.
- high_risk_detector_evidence attaches only to existing risk_entities.

## Implemented v1 Detectors

- purchase_interval_ipi: median_mad_robust_z_v1
- purchase_quantity_trend: simplified_ratio_v1
- purchase_frequency_drop: recent_base_rate_ratio_v1

## Experimental / Reserved / Interface Only

- sku_shrink: interface_only (requires_product_line_mapping)
- fulfillment_gap: experimental (reserved_three_stage_gap)
- price_competition: reserved (requires_comparable_unit_price)
- peer_contrast: reserved (requires_peer_group_quality)

## Result Tables

- detector_catalog
- daily_detector_runs
- daily_detector_clues
- high_risk_detector_evidence

## Config

- config_version: daily_detector_rules_v1
- config_path: configs/risk_algorithm_core/daily_detector_rules.yaml

## ClickHouse Sampling Guardrail

- Development ClickHouse sampling must select a bounded manufacturer set and read complete orders for those manufacturers across the configured time window.
- Row-level top sampling is forbidden because it truncates entity history and distorts detector/model outputs.