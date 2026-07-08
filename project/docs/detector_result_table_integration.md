# Detector Result Table Integration

## Scope

`project` reads detector results from Model-side result-batch tables through `risk_model_core`.
It does not run detector rules, does not import algorithm modules, and does not read raw/source
business data for detector evidence.

The read path is:

```text
front_end
-> project API
-> project detector result service
-> risk_model_core repository/service
-> result-batch parquet/csv
-> future result DB table
```

Forbidden paths:

```text
project -> risk_algorithm_core
project -> algo_main
project -> raw/source DB
front_end -> risk_model_core
front_end -> result-batch files
```

## Model Contract

The Model-side contract exposes these result-batch detector tables:

- `detector_catalog`
- `daily_detector_runs`
- `daily_detector_clues`
- `high_risk_detector_evidence`

`project` accesses them only through these `risk_model_core` repository methods:

- `list_detector_catalog`
- `list_daily_detector_runs`
- `list_daily_detector_clues`
- `list_high_risk_detector_evidence`

If a table is missing, the API returns an empty or not-ready response with warnings. The backend
does not reconstruct detector outputs from raw data.

## Product Semantics

Detector output is daily rule inspection evidence.

- `detector_score` is a rule inspection score, not probability.
- `detector_score` does not replace monthly model probability.
- `monthly_risk_probability` comes from the monthly `risk_result_batch`.
- `monthly_loss_value` comes from monthly result-batch fields.
- Non-monthly-high-risk rows in `daily_detector_clues` are daily rule clues only.
- Daily rule clues do not create new `risk_entities`.

Current detector capability status is surfaced through the catalog API. Implemented detectors are
available; `interface_only`, `experimental`, and `reserved` detectors remain visible but must not be
presented as launched production capability.

## Project API

- `GET /api/v1/detectors/catalog`
- `GET /api/v1/detectors/runs`
- `GET /api/v1/detectors/clues`
- `GET /api/v1/daily-detector/status`
- `GET /api/v1/daily-detector/clues`
- `GET /api/v1/risk-entities/{risk_entity_id}/detector-evidence`
- `GET /api/v1/detectors/config-status`

The config status endpoint is read-only. It states that detector hyperparameter changes only take
effect after the next detector inspection run, and that historical detector results are not silently
rewritten.

## Legacy Project Detector Runtime

Older `project` detector runtime/config modules are historical or internal runtime references.
Formal monthly pages and detector evidence APIs should use Model-side result-batch detector tables.
This integration does not delete legacy modules and does not use them to compute page evidence.
