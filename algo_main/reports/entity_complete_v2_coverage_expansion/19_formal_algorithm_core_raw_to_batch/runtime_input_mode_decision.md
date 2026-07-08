# Runtime Input Mode Decision

## Decision

- selected current mode: `normalized_fact_mode`
- production target mode: `formal_raw_orders_mode`
- readiness ceiling in current repository: `conditional_fact_mode_ready`

## Findings

1. SQL raw orders are not exported as a stable raw input batch in the current repository.
2. The v2 cleaned order fact is available:
   - `algo_main/data/entity_complete_v2_coverage_expansion/04_facts/fact_purchase_event.parquet`
3. The v2 entity-month fact is available:
   - `algo_main/data/entity_complete_v2_coverage_expansion/04_facts/fact_entity_month.parquet`
4. The v2 exploration feature frame is available:
   - `algo_main/data/entity_complete_v2_coverage_expansion/05_features/entity_cutoff_feature_table.parquet`

## Meaning

The formal runtime can be validated from normalized purchase facts forward. This proves the production layer can reproduce source fact/entity/feature semantics from a stable order fact input.

It does not yet prove direct SQL/raw-orders-to-fact parity. That remains a production deployment prerequisite once raw business tables are supplied through `risk_raw_input_batch`.

## Formal Readiness Rule

If all parity checks pass in `normalized_fact_mode`, readiness can be at most:

```text
conditional_fact_mode_ready
```

The system can reach:

```text
raw_orders_mode_ready
```

only after raw business orders are supplied and raw-orders-to-fact parity passes.
