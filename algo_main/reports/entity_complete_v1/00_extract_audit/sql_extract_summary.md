# SQL Extract Summary

- SQL_DATABASE_URL masked: `mssql+pyodbc://<user>:***@<host>/ylzc_gyl`
- SQL table: `BS_Agent_DingDan`
- dry_run: False
- estimate_only: False
- selected manufacturers: 1D93E15EBB9B4F14A1C18E0CD1750A0A, C458C50660B24C6B96A91FEBAAE8E5C8, 263F9947B4FA4F8DB61C9FF48D5A942A, 9701EFF559DF4862AF18CF0DC1B6962D
- selected manufacturer count: 4
- selected entity count: 1500
- selected hospital-drug choice-set pair count: 3000
- manufacturer complete extracted rows: 684674
- entity complete extracted rows: 20551
- hospital-drug choice-set extracted rows: 274685
- selected manufacturer purchase_time range: 2010-05-11 17:43:32 to 2026-06-24 22:18:04
- output manufacturer parquet: `data/entity_complete_v1/02_sql_extract/manufacturer_complete_orders.parquet`
- output entity parquet: `data/entity_complete_v1/02_sql_extract/entity_complete_orders.parquet`
- output hospital-drug choice-set parquet: `data/entity_complete_v1/02_sql_extract/hospital_drug_choice_set_orders.parquet`
- runtime seconds: 243.98
- password printed: false

## Coverage

| scope                            |   selected_manufacturer_count |   selected_entity_count |   estimated_rows |   sql_total_rows |   row_coverage_rate |   sql_total_entities |   selected_hospital_drug_pair_count |
|:---------------------------------|------------------------------:|------------------------:|-----------------:|-----------------:|--------------------:|---------------------:|------------------------------------:|
| manufacturer_complete_subset     |                             4 |                   51226 |           684674 |          2279687 |           0.300337  |               159848 |                                 nan |
| entity_complete_sample           |                            12 |                    1500 |            73273 |          2279687 |           0.0321417 |               159848 |                                 nan |
| hospital_drug_choice_set_context |                           nan |                    3059 |           274685 |          2279687 |           0.120492  |               159848 |                                3000 |

The extraction avoids row-level `SELECT TOP` sampling. Manufacturer rows are complete for selected manufacturers; entity rows are complete for selected entity keys.

## Manufacturer Substitution Caveat

Manufacturer-complete data alone can misread hospital-drug manufacturer switching as random churn. This v1 extract therefore adds `hospital_drug_choice_set_orders.parquet`: for selected `hospital_code x drug_code` pairs touched by the manufacturer subset, all manufacturer histories are extracted so downstream features can separate manufacturer-specific churn from hospital-drug demand continuation/substitution.
