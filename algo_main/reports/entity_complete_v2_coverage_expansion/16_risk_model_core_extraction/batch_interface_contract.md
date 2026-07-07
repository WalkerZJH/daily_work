# Batch Interface Contract

`risk_model_core` consumes a standard `risk_result_batch` directory.

Required files:

- `manifest.json`
- `risk_entities.parquet` or `risk_entities.csv`
- `risk_cards.parquet` or `risk_cards.csv`
- `risk_card_evidence.parquet` or `risk_card_evidence.csv`
- `risk_entity_timeline.parquet` or `risk_entity_timeline.csv`
- `hospital_aggregates.parquet` or `hospital_aggregates.csv`
- `drug_aggregates.parquet` or `drug_aggregates.csv`
- `monthly_reports.parquet` or `monthly_reports.csv`
- `proof_cases.parquet` or `proof_cases.csv`
- `work_order_reserved.parquet` or `work_order_reserved.csv`
- optional `page_payloads/*.json`

Monthly cadence is mandatory for report interfaces:

- domain object: `MonthlyReport`
- table: `monthly_reports`
- repository method: `list_monthly_reports`
- API direction: `/api/monthly-reports`

The core package must not read M closure source tables such as M1/M3/M4/M5/M7 outputs.

