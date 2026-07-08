# Current Adaptation Patch Audit

## Audit Status

- audit timestamp: 2026-07-07
- action taken: paused code adaptation; no commit made
- diff snapshot: `current_adaptation_patch.diff`
- diff scope: algorithm core, formal raw-to-batch adapter, risk algorithm configs, focused tests, and 19-stage reports
- intentionally excluded from diff snapshot: `front_end/`, `project/`, `daily_work/notes/new_ver/前后端设计草案/`

## Current Working Tree Signals

The current uncommitted patch includes:

- modified formal stage reports under `algo_main/reports/entity_complete_v2_coverage_expansion/19_formal_algorithm_core_raw_to_batch/`
- modified adapter script: `algo_main/scripts/export_current_v2_raw_input_batch_for_algorithm_core.py`
- modified configs: `configs/risk_algorithm_core/monthly_run.example.yaml`, `configs/risk_algorithm_core/monthly_run.formal.example.yaml`
- modified runtime files:
  - `risk_algorithm_core/feature_engineering.py`
  - `risk_algorithm_core/production_feature_builder.py`
  - `risk_algorithm_core/candidate_selector.py`
  - `risk_algorithm_core/monthly_runner.py`
  - `risk_algorithm_core/result_assembler.py`
  - `risk_algorithm_core/entity_builder.py`
  - `risk_algorithm_core/normalization.py`
- modified tests:
  - `tests/test_candidate_selector.py`
  - `tests/test_feature_engineering.py`
- untracked diagnostic/report artifact:
  - `algo_main/reports/entity_complete_v2_coverage_expansion/19_formal_algorithm_core_raw_to_batch/per_user_worklist_fill_strategy.md`
- untracked root fixture output:
  - `data/risk_result_batches/report_month=2026-07/batch_id=2026-07-monthly-risk-algorithm-fixture/`

There are also pre-existing dirty frontend files:

- `front_end/layout/layout.js`
- `front_end/src/layout/navigation.js`
- `front_end/vite.config.js`
- `front_end/algo-architecture.html`
- `tests/test_frontend_algorithm_architecture_page.py`

These frontend files were not included in the current algorithm diff snapshot and must not be staged or committed as part of this task.

## What The Patch Was Trying To Fix

The patch was moving toward clearing formal raw-to-batch warnings by:

1. Expanding `risk_algorithm_core/feature_engineering.py` to generate more columns that resemble the exploration feature frame.
2. Adjusting `production_feature_builder.py` missing-value behavior.
3. Adding cutoff/status passthrough behavior in `normalization.py` and `entity_builder.py`.
4. Changing `candidate_selector.py` toward a per-user 20-50 worklist rule.
5. Passing primary horizon/worklist user config through `monthly_runner.py`.
6. Making `result_assembler.py` more parquet-safe and adding worklist user metadata.
7. Updating the formal adapter/parity script so raw-to-feature and result-batch parity warnings became zero.

This creates a high semantic risk: warning removal may be caused by a new approximated production flow and relaxed parity definitions rather than true migration of the verified exploration flow.

## Algorithm Semantic Changes

High-risk changes:

- `risk_algorithm_core/feature_engineering.py`
  - The patch substantially rewrites the production feature builder.
  - It appears to implement a near-match to selected exploration features rather than directly migrating the verified `entity_complete_rebuild.py` feature functions.
  - This should not be accepted until each migrated feature is proven against the exploration source-of-truth.

- `risk_algorithm_core/production_feature_builder.py`
  - Missing-column and NaN handling changed.
  - This may affect the exact model input distribution.
  - It must be revalidated against `feature_schema.json`, `preprocessing.json`, and the exploration training pipeline.

- `risk_algorithm_core/entity_builder.py` and `risk_algorithm_core/normalization.py`
  - Cutoff end-of-day and status passthrough changes may be valid.
  - They should be retained only if they match the exploration feature build contract.

## Candidate Policy Changes

High-risk changes:

- `risk_algorithm_core/candidate_selector.py`
  - The patch changes selector behavior toward per-user minimum/maximum worklist fill.
  - This must not replace the core M1 candidate policy.
  - The business need of 20-50 rows is a presentation/workload constraint per user, not the primary recurring candidate definition.

Correct separation:

- M1 recurring candidate pool must remain tied to the verified M1 policy and business priority semantics.
- Per-user 20-50 rows should be implemented as a downstream presentation worklist cap/fill layer.
- Shortage fill should be labeled as observation or low-confidence watch, never as high risk.
- One-shot and demand-shape observation remain side channels and must not contaminate recurring churn candidates.

## Parity Judgment Changes

High-risk changes:

- `algo_main/scripts/export_current_v2_raw_input_batch_for_algorithm_core.py`
  - The patch appears to compare production features against `golden_model_feature_frame` and/or schema-aligned references in a way that can mask raw-to-feature divergence.
  - The result-batch parity logic appears to shift from reference-table parity toward runtime boundedness/readability checks.
  - Bounded output is necessary, but it is not proof of correct reproduction of the exploration flow.

Reports affected by this risk:

- `raw_to_feature_parity_report.md`
- `raw_to_feature_parity.csv`
- `full_result_batch_parity_report.md`
- `full_result_batch_parity.csv`
- `formal_algorithm_core_summary.md`
- `formal_algorithm_core_readiness_gate.md`

These should be treated as provisional and not used as final formal readiness evidence.

## Should Roll Back Or Replace

Recommended rollback/replacement candidates:

- Approximate feature rewrite in `risk_algorithm_core/feature_engineering.py`
- Candidate selector changes that make per-user 20-50 the core policy
- Parity script changes that loosen raw-to-feature or result-batch parity
- Report outputs generated after the parity semantics changed
- Tests that codify per-user fill as the core M1 selector behavior

Rollback should be done carefully in a follow-up step, preserving this audit and `current_adaptation_patch.diff` as diagnostic evidence.

## Can Keep As Diagnostics

Potentially useful diagnostics:

- Raw source inventory logic
- Raw input adapter path discovery
- Cutoff end-of-day investigation, if source-of-truth confirms it
- Generic CSV/parquet loader improvements
- Parquet-safe result write improvements, if they do not alter algorithm semantics
- Forbidden-claims and detector-disabled safety checks
- Per-user worklist fill strategy document, but only as presentation-layer design guidance

## Needs Revalidation

The following must be revalidated against source-of-truth:

- Exact feature generation from raw/fact tables
- Missing-value and dtype policies
- `one_shot_silence_months`
- H12 handling when no golden reference is available
- Whether `current_v2_raw_input_batch` is a true raw/fact source and not feature-derived
- Whether output counts should match M1/M3/M4/M5/M7 references or a documented production refactor
- Whether any status/display fields added in runtime are derived without changing probability semantics

## Current Conclusion

The current patch should not be committed as a correctness fix. It is useful as a diagnostic snapshot, but the formal path must switch back to:

```text
verified exploration source flow
-> migrate production-safe functions into risk_algorithm_core
-> prove raw source parity
-> prove raw-to-feature parity
-> prove model input parity
-> prove score parity
-> prove M1/M3/M4/M5/M7 result-batch parity
```

Until that chain is proven, `formal_second_layer_ready=true` from the current modified reports should be considered invalid/provisional.
