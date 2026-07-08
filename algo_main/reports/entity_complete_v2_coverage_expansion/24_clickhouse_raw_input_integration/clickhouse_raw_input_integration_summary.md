# ClickHouse Raw Input Integration Summary

## Scope

This stage connects `risk_algorithm_core` to the real ClickHouse source table
`gyl_data.drug_purchase_orders` through the algorithm-core raw input boundary.
It does not move raw/source database access into `risk_model_core`, `project`,
or `front_end`.

## Connection And Source

- source_system: ClickHouse
- source_database: `gyl_data`
- source_table: `drug_purchase_orders`
- connection_config: local `.env`, not committed
- raw manifest: `configs/risk_algorithm_core/clickhouse_raw_input_batch/manifest.json`
- schema mapping: `configs/risk_algorithm_core/schema_mapping.clickhouse_drug_purchase_orders.yaml`

## Source Inventory

- table rows: 57,357,962
- valid purchase_time rows after 1971-01-01: 57,357,821
- valid purchase_time min: 2010-01-01
- valid purchase_time max: 2026-06-15
- delivery_time invalid/sentinel count: 41,976,769
- received_time invalid/sentinel count: 43,261,197

Delivery/arrival time fields are therefore not safe for a delivery-time detector.

## Field Mapping Status

High-confidence mappings:

- `purchase_time` -> `order_date`
- `manufacturer_code` -> `manufacturer_code`
- `manufacturer_name` -> `manufacturer_display_name`
- `hospital_code` -> `hospital_code`
- `hospital_name` -> `hospital_name`
- `drug_code` -> `drug_code`
- `purchase_quantity` -> `order_quantity`
- `purchase_amount` -> `order_amount`
- `delivery_enterprise_code` -> `distributor_code`

Needs business confirmation:

- `generic_name` -> `drug_name`: acceptable as generic-name display, but
  `brand_name` may be needed for product display in some pages.
- `province_code/province` -> `region_code/region_name`: business region uses
  province-level code and name.
- `drug_category` -> `product_line_name`: display fallback only; not a true
  product-line or portfolio mapping.

## Smoke Raw Read

The smoke manifest limits each query to 5,000 rows.

- orders_rows: 5,000
- order_date_min: 2025-12-15 11:20:14
- order_date_max: 2025-12-15 12:21:07
- manufacturer_count: 47
- hospital_count: 1,434
- drug_count: 482
- drug_master_rows: 1,025
- hospital_master_rows: 5,000
- manufacturer_master_rows: 65

Sample outputs are under:

`algo_main/data/entity_complete_v2_coverage_expansion/15_clickhouse_raw_input_integration/`

## Monthly Algorithm Smoke

Command:

`python -m risk_algorithm_core.cli run --config configs/risk_algorithm_core/monthly_run.clickhouse_smoke.yaml`

Output batch:

`algo_main/data/entity_complete_v2_coverage_expansion/15_clickhouse_raw_input_integration/result_batches/report_month=2025-12/batch_id=2025-12-monthly-risk-algorithm-clickhouse-smoke`

Run summary:

- report_month: 2025-12
- cutoff_date: 2025-12-31
- raw_batch_id: `clickhouse_drug_purchase_orders_smoke`
- entity_rows: 13,728
- feature_rows: 13,728
- score_rows: 13,728
- selected_candidate_rows: 948
- detector_output_rows: 3,792
- risk_card_rows: 1,896
- evidence_rows: 1,896
- model_artifact_id: `xgboost_small_without_choice_set_20260707043129`
- dry_run_rule_baseline: false

`entity_display_lookup` was generated with 316 rows and
`display_name_quality=master` for all rows in this smoke batch.

## ClickHouse Write Probe

The write probe attempted to create/insert into
`risk_algorithm_core_write_probe`.

Result:

- write_status: `fallback_csv`
- fallback file:
  `algo_main/data/entity_complete_v2_coverage_expansion/15_clickhouse_raw_input_integration/clickhouse_write_fallback/risk_algorithm_core_write_probe.csv`
- observed error: HTTP 404 from ClickHouse write path

Interpretation: the current connection is valid for read. Write-back is not
confirmed; the algorithm-core output safely falls back to local parquet/csv.

## Boundary

- `risk_algorithm_core` reads raw ClickHouse source data.
- `risk_algorithm_core` produces local result batches and can attempt result
  table write-back when enabled.
- `risk_model_core` remains result-batch/result-serving only.
- `project` should read via `risk_model_core`, not through ClickHouse raw/source.
- `front_end` should consume API fields only.
