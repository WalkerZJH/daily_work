# SQL Extract Summary

- SQL_DATABASE_URL masked: `mssql+pyodbc://<user>:***@<host>/ylzc_gyl`
- SQL table: `BS_Agent_DingDan`
- dry_run: False
- estimate_only: False
- selected manufacturers: 1D93E15EBB9B4F14A1C18E0CD1750A0A, C458C50660B24C6B96A91FEBAAE8E5C8, 263F9947B4FA4F8DB61C9FF48D5A942A, 9701EFF559DF4862AF18CF0DC1B6962D, DFC52F4CCF384D849D053242EA2935F3, 43B3F24E6895475BA3EA1CD00FA74CE0
- selected manufacturer count: 6
- selected entity count: 3000
- selected hospital-drug choice-set pair count: 6000
- manufacturer complete extracted rows: 782151
- entity complete extracted rows: 124911
- hospital-drug choice-set extracted rows: 380205
- selected manufacturer purchase_time range: 2010-05-11 17:43:32 to 2026-06-24 22:18:04
- output manufacturer parquet: `data/entity_complete_v2_coverage_expansion/02_sql_extract/manufacturer_complete_orders.parquet`
- output entity parquet: `data/entity_complete_v2_coverage_expansion/02_sql_extract/entity_complete_orders.parquet`
- output hospital-drug choice-set parquet: `data/entity_complete_v2_coverage_expansion/02_sql_extract/hospital_drug_choice_set_orders.parquet`
- runtime seconds: 417.95
- password printed: false

## Coverage

| scope                            |   selected_manufacturer_count |   selected_entity_count |   estimated_rows |   sql_total_rows |   row_coverage_rate |   sql_total_entities |   selected_hospital_drug_pair_count |
|:---------------------------------|------------------------------:|------------------------:|-----------------:|-----------------:|--------------------:|---------------------:|------------------------------------:|
| manufacturer_complete_subset     |                             6 |                   65894 |           782151 |          2279687 |            0.343096 |               159848 |                                 nan |
| entity_complete_sample           |                            12 |                    3000 |           124911 |          2279687 |            0.054793 |               159848 |                                 nan |
| hospital_drug_choice_set_context |                           nan |                    7524 |           380205 |          2279687 |            0.166779 |               159848 |                                6000 |

The extraction avoids row-level `SELECT TOP` sampling. Manufacturer rows are complete for selected manufacturers; entity rows are complete for selected entity keys.

## Manufacturer Substitution Caveat

Manufacturer-complete data alone can misread hospital-drug manufacturer switching as random churn. This v1 extract therefore adds `hospital_drug_choice_set_orders.parquet`: for selected `hospital_code x drug_code` pairs touched by the manufacturer subset, all manufacturer histories are extracted so downstream features can separate manufacturer-specific churn from hospital-drug demand continuation/substitution.
