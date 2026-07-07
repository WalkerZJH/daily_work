# Raw Input Batch Contract

`risk_algorithm_core` starts from raw business input tables.

Required:

- `manifest.json`
- `orders.csv` or `orders.parquet`

Recommended:

- `drug_master`
- `hospital_master`
- `manufacturer_master`
- `distributor_master`
- `product_line_mapping`
- `price_reference`
- `delivery_events`
- `org_scope`

Reader interfaces:

- local csv/parquet reader: implemented;
- SQL reader: interface stub retained for future read-only database access;
- ClickHouse reader: interface stub retained for future read-only warehouse access.

The database reader interfaces belong here, not in `risk_model_core`.
