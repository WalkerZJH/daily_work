# Frontend Query Contract V1

Generated at: 2026-07-14

## Goal

The next frontend refactor should separate editable filter state from applied request state.

- `draftQuery`: values currently visible in controls.
- `appliedQuery`: last complete query bundle submitted to backend.
- Query execution happens only when the user clicks Apply or Query.

## Required API flow

### Manufacturer catalog

```http
GET /api/v1/my/manufacturers
```

Purpose:

- Return all manufacturers the current user may access.
- Must not shrink based on the currently selected manufacturer, date, horizon, top N, or sort.

### Page query context

```http
GET /api/v1/page-query-context/index?manufacturer_code=...
```

Purpose:

- Return lightweight valid parameter domains for the selected manufacturer.
- Include available observation dates, available horizons, available sort options, display lookup status, and detector availability by date.
- Must read prebuilt registries, not scan large result tables on every request.

Expected fields:

```json
{
  "manufacturer_code": "",
  "manufacturer_display_name": "",
  "available_observation_dates": [],
  "available_horizons": [],
  "available_sort_options": [],
  "default_query": {},
  "context_status_by_date": [],
  "warnings": []
}
```

### Applied workbench query

```http
GET /api/v1/workbench?manufacturer_code=...&observation_date=...&probability_report_month=...&detector_run_date=...&horizon=...&top_n=...&sort_by=...
```

Required complete bundle:

- `manufacturer_code`
- `observation_date`
- `probability_report_month`
- `detector_run_date`
- `horizon`
- `top_n`
- `sort_by`
- `user_id` through header or query

Response must echo:

```json
{
  "query": {
    "requested_manufacturer_code": "",
    "effective_manufacturer_code": "",
    "requested_observation_date": "",
    "effective_observation_date": "",
    "requested_horizon": "",
    "effective_horizon": "",
    "requested_sort_by": "",
    "effective_sort_by": ""
  },
  "scope": {
    "scope_applied": true,
    "manufacturer_count": 1
  }
}
```

## Invalid parameter semantics

Invalid combinations must return `422`, not silently change dates or months.

Examples:

- Invalid manufacturer/date combination: `INVALID_MANUFACTURER_OBSERVATION_CONTEXT`
- Missing horizon in selected batch: `HORIZON_NOT_AVAILABLE`
- Missing sort metric: `SORT_METRIC_NOT_AVAILABLE`
- Missing detector run for detector-only page: `DETECTOR_RUN_NOT_AVAILABLE`

Forbidden behavior:

- fallback to latest date
- fallback to default manufacturer
- fallback to primary horizon
- fallback from selected manufacturer to global data
- old request overwriting newer UI state

## Frontend state model

Recommended state:

- `manufacturerCatalog`: stable list from `/my/manufacturers`
- `draftQuery`: local edits in controls
- `pageQueryContext`: lightweight valid domains for current draft manufacturer
- `appliedQuery`: immutable snapshot used by data table requests
- `requestSequence`: monotonic sequence for race control
- `abortController`: cancels stale request groups

## Next suggested files

- `front_end/src/modules/monthly-workbench/MonthlyWorkbenchView.vue`
- `front_end/src/modules/risk-worklist/RiskEntityListView.vue`
- `front_end/src/modules/risk-worklist/RiskEntityDetailView.vue`
- `front_end/src/modules/oneshot-monitor/OneshotMonitorView.vue`
- `front_end/src/modules/monthly-demo/pageDataAdapter.js`
- `front_end/src/services/backendApi.js`

