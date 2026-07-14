# Frontend Query Refactor Baseline

Generated at: 2026-07-14

## Current entry points

- `index.html` mounts the current workbench flow.
- `clues.html` mounts the rule clue list flow.
- `clue-detail.html` mounts the rule clue or risk entity detail flow.
- `oneshot.html` mounts the one-shot terminal flow.
- Internal pages such as monthly report, proof case, and algorithm architecture keep URL query parameters through shared navigation helpers.

## Current query source

The current frontend builds query state directly from `window.location.search` through `normalizeWorkbenchQuery`.

The persisted parameters are:

- `backendBaseUrl`
- `user_id`
- `observation_date`
- `report_month`
- `run_date`
- `probability_report_month`
- `detector_run_date`
- `manufacturer_code`
- `detector_family`
- `detector_id`
- `horizon`
- `top_n`
- `sort_by`
- `demoMode`

## Current watcher chain

Workbench and clue pages bind page controls directly to the live query object. Watchers trigger loading when any of these values change:

- `observationDate`
- `horizon`
- `manufacturerCode`
- `backendBaseUrl`
- `userId`
- `demoMode`
- detector family and detector ID on clue pages

Detail pages similarly reload when:

- `horizon`
- `observationDate`
- `manufacturerCode`
- `backendBaseUrl`
- `userId`
- `demoMode`

## Current Index request fan-out

A single workbench refresh may call:

- `GET /api/v1/my/manufacturers`
- `GET /api/v1/report-context`
- `GET /api/v1/detectors/catalog`
- `GET /api/v1/workbench`
- `GET /api/v1/daily-detector/status`
- `GET /api/v1/daily-detector/clues`
- `GET /api/v1/display-lookup/status`

The requests are currently made from page loaders and `pageDataAdapter.js`. The page does not yet have a separate draft query and applied query state.

## Large-table readers

The likely large-result readers are:

- `/api/v1/workbench`
- `/api/v1/risk-entities`
- `/api/v1/daily-detector/clues`
- `/api/v1/oneshot-terminals`
- risk entity detector evidence and probability trend endpoints for detail pages

The light context readers are:

- `/api/v1/my/manufacturers`
- `/api/v1/report-context`
- `/api/v1/display-lookup/status`
- `/api/v1/daily-detector/status`
- `/api/v1/detectors/catalog`

## Current risks

- Changing a simple filter can trigger several API calls immediately.
- The same URL query acts as both draft and applied state.
- Invalid parameter combinations are partially corrected through report context application.
- Older requests can still return after newer user input unless guarded by page-level sequence checks.
- The production backend is now Parquet-only, so frontend context APIs should avoid repeatedly forcing large table scans.

