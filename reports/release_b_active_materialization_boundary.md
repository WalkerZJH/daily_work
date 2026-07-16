# Release B active materialization boundary

Checked at 2026-07-16 (Asia/Shanghai). This record defines isolation only; it does not diagnose or accept the running materialization.

## Live processes

| PID | run_id | date range |
|---:|---|---|
| 3004 | zz-2025-admin-full-v1-q1 | 2025-01-02..2025-02-14 |
| 32792 | zz-2025-admin-full-v1-q1b | 2025-02-15..2025-03-31 |
| 12844 | zz-2025-admin-full-v1-q2 | 2025-04-01..2025-05-15 |
| 9712 | zz-2025-admin-full-v1-q2b | 2025-05-16..2025-06-30 |
| 18896 | zz-2025-admin-full-v1-q3 | 2025-07-01..2025-08-15 |
| 32076 | zz-2025-admin-full-v1-q3b | 2025-08-16..2025-09-30 |
| 9620 | zz-2025-admin-full-v1-q4 | 2025-10-01..2025-11-15 |
| 16732 | zz-2025-admin-full-v1-q4b | 2025-11-16..2025-12-31 |

All commands use:

- input: `algo_main/data/entity_complete_v2_coverage_expansion/11_business_detector_adaptation/cleaned_detector_input/batch_id=cleaned-detector-facts-v2-20260716`
- output root: `data/project_result_batches`
- `--resume-existing`
- the 10 Release A Detector ids

## ACTIVE_MATERIALIZATION_PATHS

- `data/project_result_batches/.detector_staging`
- component and staging paths under `data/project_result_batches/detector_run_date=2025-01-02` through `detector_run_date=2025-12-31` for the eight run ids above
- running range-status and registry-adjacent files under the same output root

Release B implementation and tests must not read or write Parquet in these paths, must not update the observation registry, and must not start, stop, pause, resume, publish, or validate these runs. Stable verification is limited to fixtures and the previously published `detector_run_date=2026-01-01` with its exact `report_month=2025-12` association.

## Frontend design source

The attached design was found at `daily_work/notes/new_ver/前端美化/clues页面美化策略（待实现）.md` and was read in full. Release B uses it as the Clues filter interaction authority: four category cards, Draft-only browsing, explicit Applied queries, disabled Detector visibility, keyboard semantics, and reduced-motion support. Its rule-only scope remains separate from the entity-level detail extension required by the Release B implementation prompt.

## Verification deviation

The isolated Release B tests used only in-memory and temporary-path fixtures. A later full-project test run unintentionally executed two pre-existing tests whose helper explicitly set `RISK_RESULT_BATCH_ROOT` to `data/project_result_batches` and queried the formal `2025-12-05` Detector context. This was read-only, but it did not comply with the stricter no-read boundary above. No Parquet, manifest, staging, registry, or process state was written or controlled.

A process-only check after discovery found PIDs 9620, 9712, 16732, 32076, and 32792 still running and responding. PIDs 3004, 12844, and 18896 were no longer present at that later check; no attempt was made to diagnose or alter their completion state.

The continuation pass repeated only the permitted command-line process query. It found materialization PIDs 9712 (`q2b`, 2025-05-16..2025-06-30), 32076 (`q3b`, 2025-08-16..2025-09-30), and 16732 (`q4b`, 2025-11-16..2025-12-31). The PowerShell query process matched its own search text and was excluded. All previously recorded 2025 paths remain conservatively classified as `ACTIVE_MATERIALIZATION_PATHS`; no output file or directory was inspected in this continuation pass.
