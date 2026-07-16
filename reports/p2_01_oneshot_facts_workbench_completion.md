# P2-01 One-shot facts workbench completion

Status: `DONE` on 2026-07-16.

## Delivered contract

- The formal source is the Manifest-declared `oneshot_terminals.parquet` (`oneshot_terminal_v1`). A missing declaration or file returns `ONESHOT_RESULT_NOT_AVAILABLE`; it never falls back to Recurring or `risk_entities`.
- `GET /api/v1/oneshot-terminals` now supports `page`, `page_size`, `sort_by`, and `sort_order`, and returns total rows and total pages.
- Allowed sorts are formal facts only: `first_purchase_date`, `first_purchase_amount`, and `days_since_first_purchase`. The default is newest first-purchase date first.
- Customer responses and the One-shot page no longer expose repurchase propensity, high-propensity counts, expected repurchase amount, model-driven priority, or ranking-basis copy.
- The workbench retains hospital, drug, manufacturer, region, first-purchase date, amount at the first-purchase time point, days since first purchase, report month, cutoff date, and result-batch identity.
- The page has explicit loading, empty, error, and formal-result-unavailable states, plus retry, query controls, and server pagination.

## Boundaries preserved

- No One-shot detail page was added.
- No One-shot model was trained, recalculated, or integrated.
- No new One-shot materialization was added and no historical batch was changed.
- Detector 2025 daily materialization remains an independent parallel task and did not gate P2-01.

## Verification

- Targeted API, model-serving boundary, and frontend contract tests: `33 passed`.
- Frontend production build: passed with `npm run build`.
- Read-only formal-batch check against `2025-12-monthly-risk-algorithm-full-recurring-v3`: 6,044 One-shot facts, correct fact-only item keys, pagination, and newest-date ordering.
- Wider `project/tests` run: `189 passed, 7 failed`. The seven remaining failures are pre-existing Detector/environment/Workbench-contract failures outside the P2-01 path.

Baseline: branch `main`, starting commit `af3ec42b04043a696b226dd3ae890a527c3624b0`. Existing uncommitted Detector and batch-discovery work was preserved and not included in this module.
