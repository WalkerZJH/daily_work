# Report Context Resolution Summary

## Current Batch Inventory

- Monthly result batches found: 1
- Available report months: `2025-12`
- Available manifest run dates: `2026-07-07`
- Available detector run dates recorded in `daily_detector_runs`: `2026-07-08`
- Current frontend date-resolution run date uses the manifest-level `run_date`, not a fabricated current date.

The current model-side result inventory is below the frontend multi-date target:

- Target monthly result batches: 3 months
- Current monthly result batches: 1 month
- Target detector daily run dates: about 90 dates
- Current detector daily run dates: 1 date

No additional months or daily detector runs were fabricated in this task.

## Added Files

- `report_context.json` in the formal batch directory.
- `available_report_contexts.csv` at the formal result-batch root.

## Resolution Semantics

`risk_model_core` now exposes:

- `manifest_context()`
- `list_available_report_contexts()`
- `resolve_report_context(requested_report_month=None, requested_run_date=None, requested_horizon=None)`

Resolution fields include:

- `requested_report_month`
- `effective_report_month`
- `requested_run_date`
- `effective_run_date`
- `requested_horizon`
- `effective_horizon`
- `date_resolution_status`
- `available_report_months`
- `available_run_dates`
- `available_horizons`
- `warnings`
- `caveats`

Allowed resolution statuses:

- `exact_match`
- `fallback_to_latest_available`
- `fallback_to_latest_report_month`
- `fallback_to_latest_detector_run`
- `no_available_batch`

## Current Expected Behavior

- Requesting `report_month=2025-12` and `run_date=2026-07-07` returns `exact_match`.
- Requesting today's run date returns `fallback_to_latest_available`.
- The effective report month is `2025-12`.
- The effective run date is `2026-07-07`.
- The model layer does not claim that today's daily detector result exists.

## Boundary

This is a result-batch serving feature only:

- no `project/` changes;
- no `front_end/` changes;
- no raw/source database reads;
- no new detector result generation;
- no fake month or day backfill;
- no demo/mock fallback.

