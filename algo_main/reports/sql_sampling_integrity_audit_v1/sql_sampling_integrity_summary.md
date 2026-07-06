# SQL Sampling Integrity Summary

## Scope

This audit checks whether the local alive-prediction data is an entity-complete history extract or a row-level SQL sample. It only profiles data and SQL aggregates; it does not train or tune any model.

## Data Sources

- Local source used: `C:\Users\admin\Myprojects\for_git\algo_main\data\04_facts\alive_prediction\fact_purchase_event__drug_code.parquet`
- SQL status: connected
- Local rows: 100000
- Local purchase_time range: 2010-01-07 to 2025-12-22
- SQL total rows: 2279687
- SQL purchase_time range: 2010-01-03 to 2026-06-25
- Sampled entities for SQL history audit: 500

## Key Findings

- Current notebook/pipeline evidence is consistent with row-level sampling: `sample_mode=True`, `max_rows=100000`, and `SELECT TOP (...)`.
- TOP N / ordered sample risk: high
- Entity history incomplete risk: high
- Entity history complete rate: 0.0140
- Mean / median order-count coverage: 0.0978 / 0.0606
- Median first-purchase lag days: 219.5000
- Median last-purchase gap days: 471.5000
- Manufacturer skew risk: true
- Time skew risk: false
- Entity-age skew risk: true
- Interval feature distortion risk: high
- Model-result contamination risk: likely

## Answers To Core Questions

1. Current local data is strongly suspected to originate from SQL row-level TOP N sampling because the notebook and pipeline use that path.
2. Entity-complete coverage is 0.0140 when SQL evidence is available; if SQL is unavailable, this remains unproven.
3. For sampled entities, SQL-vs-local history gaps are written to `entity_history_completeness_audit.csv` and `sampled_entity_sql_history_gap.csv`.
4. Time, manufacturer, and entity-age bias checks are written to the `sampling_bias_*` CSV files.
5. Low AUC / weak rank ordering can be contaminated by incomplete entity history when order counts, observed months, recency, interval, ADI, CV2, and labels are computed on truncated histories.
6. Recommended next extraction path: manufacturer_complete_then_entity_complete.

## Model Impact Analysis

If entity histories are truncated, `purchase_count_asof_cutoff`, `active_month_count_asof_cutoff`, `months_observed_asof_cutoff`, `months_since_first_purchase_asof_cutoff`, median interval, ADI/CV2, and frequency-decay features can all be biased. Labels can also be distorted when the apparent absence of future purchases is caused by extraction boundaries rather than real non-repeat behavior.

That can explain low global logistic AUC, low candidate-level AUC, interval baseline coverage gaps, high history_not_available or cold-start rates, inflated intermittent/lumpy classification, and apparently acceptable ECE with weak ranking.

## Limitations

- SQL connection failure reason: none
- This audit does not export full SQL detail and only samples entity-level history aggregates.
