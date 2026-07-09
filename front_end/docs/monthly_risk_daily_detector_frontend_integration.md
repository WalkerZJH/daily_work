# Monthly Risk + Daily Detector Frontend Integration

## Backend contract discovery

Current local repository contains backend commit `47d7d99 connect project detector APIs to result batch tables`.

Discovered project API endpoints:

- `GET /api/v1/my/manufacturers`
- `GET /api/v1/workbench`
- `GET /api/v1/risk-entities`
- `GET /api/v1/risk-entities/{entity_id}`
- `GET /api/v1/risk-entities/{entity_id}/probability-trend`
- `GET /api/v1/detectors/catalog`
- `GET /api/v1/detectors/runs`
- `GET /api/v1/detectors/clues`
- `GET /api/v1/daily-detector/dates`
- `GET /api/v1/daily-detector/status`
- `GET /api/v1/daily-detector/clues`
- `GET /api/v1/risk-entities/{risk_entity_id}/detector-evidence`
- `GET /api/v1/detectors/config-status`

Core support endpoints remain:

- `GET /api/v1/oneshot-terminals`
- `GET /api/v1/monthly-reports`
- `GET /api/v1/proof-cases`

## Frontend connection status

Implemented in `front_end/src/services/backendApi.js`:

- Manufacturer scope: used by the workbench, clues, and detail selectors.
- Workbench query: sends `manufacturer_code`, `report_month`, `run_date`, `horizon`, `top_n`, and `sort_by`.
- Risk entity query/detail: sends the same customer-facing scope and selected horizon.
- Daily detector dates: used by the workbench, clues, and detail date selectors.
- Detector catalog: connected when the project API is reachable.
- Detector runs: API client method added; not required for the current visible page state.
- Detector clues: used as compatibility fallback when the daily endpoint is unavailable.
- Daily detector status: connected for workbench/report/clues readiness.
- Daily detector clues: primary data source for the all-clues page when readiness is true.
- Risk entity detector evidence: connected for monthly high-risk detail pages when available.
- Detector config status: API client method exists; current customer pages do not surface internal configuration wording.
- Probability trend: method reserved; current page uses demo fallback if the backend endpoint is absent.

Fallback behavior:

- `ready=false`, 404, timeout, or network failure returns demo/mock state.
- Fallback is normal and not displayed as a system error.
- Mock data follows the same product semantics as the backend contract.

## Product wording applied

- Main workbench shows monthly high-risk objects.
- Monthly risk probability is presented as stable monthly probability.
- Daily page changes come from rule inspection status and rule clues.
- Detector score is rendered as `规则巡检分`.
- Value ranking is rendered as `涉及金额`.
- All-clues page distinguishes `月报高风险对象` and `仅规则命中`.
- Detector-only clues are shown as daily rule clues, not as monthly high-risk objects.

## Page changes

- `index.html`: monthly high-risk workbench plus manufacturer, daily run date, horizon, Top N, sort controls, and daily detector summary.
- `clues.html`: all daily rule clues with filters for all / monthly high-risk / rule-only.
- `clue-detail.html`: dual-mode detail page for monthly risk evidence or rule-only clue detail; horizon changes refresh probability, involved amount, trend, and evidence.
- `oneshot.html`: keeps the page to first-purchase facts unless the backend returns real reason or evidence.
- `dashboard.html`: hidden from the primary navigation.
- `backtest.html`: displays involved amount and removed model calibration metric display.
- `algo-architecture.html`: retained algorithm chain explanation while removing customer-facing model metric wording.

## Source boundary confirmation

The frontend uses project APIs and local demo/mock data only. It does not read local formal result files, algorithm-side static outputs, model packages, or leadership prototype folders. The leadership prototype folder is already ignored at repository level and is not part of frontend build or tests.
