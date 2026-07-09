# Backend Model Contract Check

## Status

Superseded blocker. The earlier stop was caused by `RISK_RESULT_BATCH_DIR` not
being set, which made the backend check fall back to an old local fixture. That
old fixture is not the formal Model contract for the current backend task.

Current backend checks must use only the explicit formal result batch path from
`RISK_RESULT_BATCH_DIR`.

## Formal Batch Path Used

```text
C:\Users\admin\Myprojects\for_git\algo_main\data\entity_complete_v2_coverage_expansion\13_formal_algorithm_core_raw_to_batch\formal_result_batches\report_month=2025-12\batch_id=2025-12-monthly-risk-algorithm-formal-v2-raw
```

## Formal Batch Readiness

The formal batch path exists and includes:

- `manifest.json`
- `report_context.json`
- `risk_entities.csv`
- `detector_catalog.csv`
- `daily_detector_runs.csv`
- `daily_detector_clues.csv`
- `high_risk_detector_evidence.csv`
- `monthly_reports.csv`
- `proof_cases.csv`
- `entity_display_lookup.csv`

The formal result-batch root also includes `available_report_contexts.csv`, which
is used to resolve requested frontend dates to the latest available batch/run.

Current observed row counts:

- `risk_entities`: 1291
- `detector_catalog`: 7
- `daily_detector_runs`: 1
- `daily_detector_clues`: 0
- `high_risk_detector_evidence`: 0
- `monthly_reports`: 1
- `proof_cases`: 0
- `entity_display_lookup`: 634

Observed report context:

- requested `run_date=2026-07-09` falls back to effective detector run date
  `2026-07-08`.
- `effective_batch_run_date` remains `2026-07-07` for batch/report context.
- `report_month=2099-01` falls back to effective report month `2025-12`.

`daily_detector_clues=0`, `high_risk_detector_evidence=0`, and `proof_cases=0`
are valid states. Backend APIs return `200` with empty lists rather than
creating mock rows or treating this as a Model failure.

## Backend Rule

Formal mode is active unless:

```text
ALLOW_MOCK_PAYLOADS=true
```

In formal mode, a missing or unreadable `RISK_RESULT_BATCH_DIR` must not fall
back to local fixtures or demo payloads. APIs should return `ready=false`, an
empty payload, or an explicit request error depending on endpoint semantics.
