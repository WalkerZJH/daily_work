# Model Core Result Serving Boundary

## Role

`risk_model_core` is the result-batch reading and serving layer. It reads a
standard `risk_result_batch` or equivalent result-serving tables and exposes
stable repository, service, and page-payload helpers for the backend.

It does not read source business tables and does not run the algorithm.

## Allowed Inputs

- `risk_result_batch` files, including the standard tables in `STANDARD_TABLES`.
- Equivalent result-serving tables in a future warehouse or ClickHouse backend.
- Backend-provided filters such as `manufacturer_codes`, `report_month`,
  `horizon`, and `candidate_type`.

## Forbidden Inputs

- raw/source business database tables;
- raw orders;
- purchase-event fact builders;
- entity-cutoff feature tables;
- SQL connection strings;
- model training or feature-engineering modules.

Raw/source database access belongs to `risk_algorithm_core` or upstream data
production jobs, not to `risk_model_core`.

## User Scope

`risk_model_core` does not resolve user permissions. The project backend owns
`org_scope`, salesperson routing, regional-manager routing, and any other
business permission rule.

The backend may pass a resolved `manufacturer_codes: list[str]` into
`risk_model_core`. Model-core filters and returns rankable rows, plus
`available_count`, `returned_count`, and `shortage_count` metadata. It does not
decide whether to add observation or one-shot rows when a backend workbench has
fewer items than requested.

## Dynamic Page Payloads

If a batch already contains `page_payloads`, `PagePayloadBuilder` reads those
files first. If a page payload is absent, it now constructs payloads from the
standard result tables.

Dynamic construction:

- reads only result-batch tables;
- does not recalculate scores;
- does not run detectors;
- does not resolve true user permissions;
- does not use demo fallback as the formal path;
- preserves optional ranking fields when they exist in `risk_entities`;
- does not fabricate missing optional ranking fields.

## Entity Display Lookup

`entity_display_lookup` is a monthly result-batch sidecar table produced by
`risk_algorithm_core`. It is part of the standard result-serving boundary, not a
frontend static mapping and not a model-core raw-data lookup.

Production ownership:

- `risk_algorithm_core` builds the table from the monthly result entities plus
  normalized raw input and dimension tables when available.
- `risk_result_contracts` validates the table presence, required schema, and
  uniqueness on `tenant_id`, `report_month`, `manufacturer_code`,
  `hospital_code`, and `drug_group`.
- `risk_model_core` reads the table from the batch via
  `load_entity_display_lookup(...)`.
- `project` should join this table through `risk_model_core` when building API
  payloads.
- `front_end` should consume display fields returned by API responses.

The table contains:

- manufacturer, hospital, drug, product-line, and region display names;
- stable code fields for drilldown and debugging;
- `display_name_source` and `display_name_quality`;
- `source_raw_batch_id` and `updated_at` for auditability.

Fallback policy:

- prefer master/dimension table names;
- then use names already carried by the result batch or normalized order facts;
- finally use code fallback and mark `display_name_quality=code_fallback`.

The current formal batch has `entity_display_lookup.csv` generated from the
existing result batch fields because no raw/dim source is read by this model-side
task. The table is still valid for result serving and can be regenerated with
stronger master-table quality during the next monthly algorithm run.

## ClickHouse Repository

`ClickHouseRiskResultRepository` is a result-table repository placeholder. It is
reserved for serving `STANDARD_TABLES` or equivalent result-serving tables. It is
not a raw/source repository.

## Current Status

- result-batch reading: ready;
- entity display lookup table: ready as a result-batch sidecar;
- dynamic payload fallback from standard tables: ready;
- user-scope permission resolution: backend responsibility;
- backend workbench sizing: backend responsibility;
- demo fallback: not used as the formal result-serving path.
