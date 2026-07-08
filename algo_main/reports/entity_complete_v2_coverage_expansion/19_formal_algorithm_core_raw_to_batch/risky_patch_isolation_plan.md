# Risky Patch Isolation Plan

## Scope

This plan isolates the current uncommitted formal algorithm core adaptation patch. The patch removed warnings, but it also changed feature engineering, candidate selection, and parity semantics. Those changes are not acceptable as formal second-layer readiness evidence.

## Current Uncommitted Files In Scope

Runtime / adapter / config / tests:

- `algo_main/scripts/export_current_v2_raw_input_batch_for_algorithm_core.py`
- `configs/risk_algorithm_core/monthly_run.example.yaml`
- `configs/risk_algorithm_core/monthly_run.formal.example.yaml`
- `risk_algorithm_core/candidate_selector.py`
- `risk_algorithm_core/entity_builder.py`
- `risk_algorithm_core/feature_engineering.py`
- `risk_algorithm_core/monthly_runner.py`
- `risk_algorithm_core/normalization.py`
- `risk_algorithm_core/production_feature_builder.py`
- `risk_algorithm_core/result_assembler.py`
- `tests/test_candidate_selector.py`
- `tests/test_feature_engineering.py`

Formal readiness reports affected by the risky patch:

- `formal_algorithm_core_progress.md`
- `formal_algorithm_core_readiness_gate.md`
- `formal_algorithm_core_summary.md`
- `full_result_batch_parity.csv`
- `full_result_batch_parity_report.md`
- `raw_to_feature_parity.csv`
- `raw_to_feature_parity_report.md`

Diagnostic artifacts to keep:

- `current_adaptation_patch.diff`
- `current_adaptation_patch_audit.md`
- `source_of_truth_flow_map.md`
- `source_of_truth_flow_map.csv`
- `per_user_worklist_fill_strategy.md`

Out of scope and not to be touched:

- `project/`
- `front_end/`
- `daily_work/notes/new_ver/前后端设计草案/`

## High-Risk Algorithm Semantic Changes

1. `risk_algorithm_core/feature_engineering.py`
   - Contains an approximate feature rewrite intended to reduce raw-to-feature warnings.
   - Must not be accepted until replaced by migrated source-of-truth functions and parity tests.

2. `risk_algorithm_core/production_feature_builder.py`
   - Changes missing-value and dtype behavior.
   - Must be reintroduced only if it matches `feature_schema.json` and training preprocessing.

3. `risk_algorithm_core/candidate_selector.py`
   - Mixes per-user 20-50 display-fill requirements into core candidate selection.
   - Must be restored and later split into core M1 policy plus downstream presentation worklist fill.

4. Formal adapter/parity script
   - Changes parity reporting toward runtime constraint checks rather than reference equality.
   - Must be restored before implementing strict fact/entity/feature/model/M-stage parity.

5. Readiness reports
   - Current `formal_second_layer_ready=true` must be treated as provisional and invalid for formal acceptance.

## Can Keep As Diagnostics

- Raw source inventory findings.
- Source-of-truth map.
- Patch diff.
- Patch audit.
- Per-user fill strategy as presentation-layer guidance only.
- Detector disabled / forbidden-claims checks, if later re-added without changing algorithm semantics.

## Isolation Action

1. Keep the diff and audit files.
2. Restore high-risk runtime/config/test/report files to the pre-risk-patch state using targeted restore.
3. Rebuild the formal algorithm core from source-of-truth migration rather than patching the approximated path.
4. Add strict parity layers:
   - fact parity
   - entity-month parity
   - feature parity
   - model input parity
   - score parity
   - M1/M3/M4/M5/M7 parity
   - risk_result_batch readability

## Commit Policy

Do not commit the risky runtime patch. Only commit once source-of-truth migration and strict parity reporting are in place, or commit reports only if implementation remains blocked.
