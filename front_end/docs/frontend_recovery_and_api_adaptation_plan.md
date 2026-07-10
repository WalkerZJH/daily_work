# Frontend Recovery And API Adaptation Plan

## Current Pages

- `index.html`: Vite-mounted risk workbench / today focus.
- `dashboard.html`: Vite-mounted monthly report and batch page.
- `clues.html`: Vite-mounted daily rule clues page.
- `clue-detail.html`: Vite-mounted risk entity or detector clue detail page.
- `oneshot.html`: Vite-mounted one-shot terminal monitor.
- `backtest.html`: Vite-mounted historical hit review page.

## Missing Pages To Restore

- `algo-architecture.html`: restore as a Vite-mounted internal algorithm chain explanation page.
- `algo-config.html`: restore as a Vite-mounted internal detector configuration/status placeholder.
- `verify.html`: restore as an internal placeholder for recovery verification and feedback.
- `distributor.html`: restore as an internal placeholder for distributor alert work.
- `order-detail.html`: restore as an internal placeholder for order detail inspection.

No existing Vite page or Vue module should be deleted for this recovery. Internal pages should be hidden from the customer navigation unless `internalMode=true`.

## Customer Main Navigation

- `index.html`: risk workbench / today focus.
- `clues.html`: daily rule clues.
- `oneshot.html`: one-shot terminal monitor, with cautious wording.

## Internal Pages

- `dashboard.html`: monthly reports and batches.
- `backtest.html`: historical hit review.
- `algo-architecture.html`: algorithm chain explanation.
- `algo-config.html`: detector/runtime configuration status.
- `verify.html`: recovery verification placeholder.
- `distributor.html`: distributor alert placeholder.
- `order-detail.html`: order detail placeholder.

These pages remain URL-addressable and Vite-mounted, but are shown in navigation only when internal mode is enabled.

## Current Project API Calls

The frontend service layer currently exposes Project API methods for:

- `GET /api/v1/report-context`
- `GET /api/v1/my/manufacturers`
- `GET /api/v1/workbench`
- `GET /api/v1/risk-entities`
- `GET /api/v1/risk-entities/{risk_entity_id}`
- `GET /api/v1/risk-entities/{risk_entity_id}/probability-trend`
- `GET /api/v1/daily-detector/status`
- `GET /api/v1/daily-detector/clues`
- `GET /api/v1/detectors/catalog`
- `GET /api/v1/detectors/runs`
- `GET /api/v1/risk-entities/{risk_entity_id}/detector-evidence`
- `GET /api/v1/display-lookup/status`
- `GET /api/v1/detectors/config-status`
- `GET /api/v1/runtime-profile`

The same service file still contains legacy `/api/v0/*` helpers for internal/debug tools. Formal risk pages must not use those helpers.

## Demo, Mock, And Static Dependencies

- Formal `pageDataAdapter.js` no longer imports `demoData` directly.
- Demo data is isolated in `demoPageDataAdapter.js` and should only load through dynamic demo mode.
- Formal mode should return empty/interface-not-ready states on API failure.
- Existing demo payloads remain available only when `demoMode=true`.
- Existing views must avoid importing static demo creator functions from the formal adapter.

## Test Contract Updates

The old cleanup contract that required internal pages to be absent is obsolete. The new contract should verify:

- Legacy static assets remain absent: `app.js`, `styles.css`, and `layout/layout.js`.
- Restored internal pages are Vite-mounted with `<div id="app"></div>` and `/src/main.js`.
- Restored pages are present in `vite.config.js`.
- Customer navigation and internal navigation are separated by `internalMode`.
- Formal adapters do not import demo data or use static business rows as fallback.
- URL context parameters are preserved across page links.
- Frontend code does not depend on local model, result batch, or prototype paths.
