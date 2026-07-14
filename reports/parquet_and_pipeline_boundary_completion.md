# Parquet and Pipeline Boundary Completion

Generated at: 2026-07-14

## 1. Current Facts

- Current batch root: `data/project_result_batches`
- Current report months: `2025-09`, `2025-10`, `2025-11`, `2025-12`
- Current batch IDs: `YYYY-MM-monthly-risk-algorithm-formal-v2-raw`
- Current storage format: Parquet-only for formal batch files under `data/project_result_batches`
- Current batch CSV count: `0`
- Current root CSV count: `0`
- Current batch Parquet count: `84`
- Current registry files:
  - `available_observation_contexts.parquet`
  - `available_observation_contexts.json`
  - `observation_registry.parquet`
  - `manufacturer_observation_registry.parquet`
  - `registry_rebuild_status.json`
- Current API read root: Project API was started with `RISK_RESULT_BATCH_ROOT=data/project_result_batches`.
- Current lookup status from live API: `ready`.
- Current detector coverage from live API:
  - `2025-12-01`: probability batch available, detector run available.
  - `2025-12-05`: probability batch available, detector run available.
- Old conflicting logs are not used as facts. Current file scan and live API response are the facts for this report.

Note: `reports/current_production_state_baseline.json` was first generated before migration, then refreshed after migration during live API verification. The retained post-migration snapshot is `reports/current_production_state_after_parquet_migration.json`. Pre-migration CSV facts are preserved in `reports/parquet_only_migration_report.json` and in the command output: 1 root CSV, 84 batch CSV, 20 batch Parquet before migration.

## 2. Parquet-only Migration

Writer changes:

- Added `risk_result_contracts.parquet_io.write_production_parquet`.
- `risk_algorithm_core.result_assembler` now writes formal tables through the production Parquet writer.
- `scripts/generate_multi_month_formal_batches.py` now forces Parquet output for formal tables, detector tables, registry, and run reports.

Reader changes:

- `risk_model_core.repositories.ParquetRiskResultRepository` now reads standard production tables from `.parquet` only.
- `risk_model_core.validation` now reads production validation tables from `.parquet` only.
- `risk_result_contracts.validation` now rejects same-name `.csv` beside formal `.parquet`.

Manifest validation:

- `risk_result_contracts.manifest` requires `data_backend=parquet`.
- `risk_model_core.manifest` requires `data_backend=parquet` for production repository loads.
- Batch validation checks declared table paths end in `.parquet`, files exist, and manifest row counts match Parquet metadata.

Atomic write strategy:

- Writes to same-directory temp file.
- Reopens written Parquet metadata for row count and schema validation.
- Uses atomic replace after validation.
- Deletes temp file on failure.
- Does not create CSV on failure.

Migration summary:

- CSV converted to Parquet: `48`
- Existing Parquet duplicates kept: `36`
- Formal CSV deleted from batch dirs: `84`
- Root registry CSV removed after Parquet registry existed.
- Non-formal CSV reports inside batch dirs were converted to Parquet or removed from the formal CSV surface.

## 3. Pipeline Boundaries

Stage A: `monthly_prediction`

- Entry: `python -m production_pipeline.run_monthly_prediction --report-month YYYY-MM --model-artifact-id <id> --output-root data/project_result_batches`
- Inputs: formal source data, explicit artifact ID, explicit report month.
- Outputs: future monthly core result batch.
- Allowed to modify: new monthly batch only.
- Forbidden implicit call: `load_current_model_artifact`.
- Status: boundary implemented; execution intentionally blocked unless `--force-repredict`.

Stage B: `daily_detector`

- Entry: `python -m production_pipeline.run_daily_detector --batch-dir <existing_batch_dir> --observation-date YYYY-MM-DD`
- Inputs: existing batch and future `detector_input_snapshot.parquet`.
- Outputs: detector tables and detector metadata only.
- Allowed to modify: `detector_catalog.parquet`, `daily_detector_runs.parquet`, `daily_detector_clues.parquet`, `high_risk_detector_evidence.parquet`, detector metadata.
- Forbidden calls: `ArtifactRiskScorer.score`, `load_current_model_artifact`, `BoundedCandidateSelector.select`, `MonthlyRiskRunner.run`.
- Status: implemented as safe blocker. Current blocker is `DETECTOR_INPUT_SNAPSHOT_MISSING`.

Stage C: `entity_display_lookup`

- Entry: `python -m production_pipeline.refresh_entity_display_lookup --batch-dir <existing_batch_dir>`
- Inputs: existing `entity_display_lookup.parquet`.
- Outputs: refreshed lookup and lookup refresh metadata.
- Forbidden calls: model scoring and candidate selection.
- Status: implemented and verified on 2025-12 batch; immutable core hashes unchanged.

Stage D/E: `observation_registry` and `manufacturer_observation_registry`

- Entry: `python -m production_pipeline.rebuild_observation_registry --batch-root data/project_result_batches`
- Inputs: existing manifests, risk entities, display lookup, detector runs.
- Outputs: root registries.
- Forbidden calls: model scoring, detector execution, batch table mutation.
- Status: implemented and run. Output rows: 123 observation contexts, 1230 manufacturer observation contexts.

Stage F: `full_pipeline`

- Entry: not implemented in this round.
- Status: deferred by request; no historical model prediction was run.

## 4. Immutability Verification

- Monthly model prediction was not executed.
- Model artifact ID remains: `xgboost_small_without_choice_set_20260713062634`.
- Four migrated batches passed `risk_result_contracts.validate_result_batch`.
- Four migrated batches passed `risk_model_core.validation.validate_batch`.
- Display lookup refresh verified unchanged hashes for:
  - `risk_entities.parquet`
  - `risk_entity_horizon_profiles.parquet`
  - `monthly_reports.parquet`
  - `daily_detector_runs.parquet`
  - `daily_detector_clues.parquet`
- CSV to Parquet changes alter file hashes by design. Business equivalence was checked by row counts, schema validation, required columns, key uniqueness, and live API behavior.

## 5. Frontend Next-stage Contract

Reports generated:

- `reports/frontend_query_refactor_baseline.md`
- `reports/frontend_query_contract_v1.md`

Current finding:

- Page controls still use live URL query as both draft and applied state.
- A filter change can trigger multiple API requests.
- Large-table requests include workbench, risk entities, detector clues, one-shot terminals, detail evidence, and trend endpoints.

Next-stage target:

- Add `draftQuery`.
- Add `appliedQuery`.
- Add lightweight `page-query-context` API.
- Submit complete Query Bundle only when user clicks Apply or Query.
- Invalid combinations return `422`; no silent date/month/manufacturer/horizon fallback.
- Old requests must not overwrite newer state.

## 6. Environment

Current runtime snapshot:

- Python: `3.13.9`
- scikit-learn: `1.7.2`
- numpy: `2.3.5`
- pandas: `2.3.3`
- pyarrow: `21.0.0`
- xgboost: `3.3.0`
- joblib: `1.5.2`

Files added:

- `environment.production.yml`
- `requirements.production.lock`

Blocker:

- The current artifact manifest does not record runtime package versions. It records artifact ID and model metadata, but not Python/scikit-learn/numpy/pandas/pyarrow/xgboost/joblib requirements.

## 7. File List

Added:

- `risk_result_contracts/parquet_io.py`
- `production_pipeline/__init__.py`
- `production_pipeline/common.py`
- `production_pipeline/run_monthly_prediction.py`
- `production_pipeline/run_daily_detector.py`
- `production_pipeline/refresh_entity_display_lookup.py`
- `production_pipeline/rebuild_observation_registry.py`
- `scripts/collect_current_production_state.py`
- `scripts/migrate_project_result_batches_to_parquet_only.py`
- `tests/test_parquet_only_production_contract.py`
- `environment.production.yml`
- `requirements.production.lock`
- reports listed above.

Modified:

- `risk_algorithm_core/result_assembler.py`
- `scripts/generate_multi_month_formal_batches.py`
- `risk_result_contracts/__init__.py`
- `risk_result_contracts/manifest.py`
- `risk_result_contracts/validation.py`
- `risk_model_core/manifest.py`
- `risk_model_core/repositories.py`
- `risk_model_core/validation.py`
- `tests/test_multi_month_formal_batches_generated.py`

Formal data changed on disk:

- Removed formal CSV files from `data/project_result_batches`.
- Added/kept Parquet files for all current formal tables.
- Added root registry Parquet files.

## 8. Tests and Live API

Commands run:

- `pytest -q tests/test_parquet_only_production_contract.py`
  - Result: 6 passed.
- `python -c "<validate all four batches with risk_result_contracts and risk_model_core>"`
  - Result: all four batches validated.
- `pytest -q tests/test_parquet_only_production_contract.py tests/test_multi_month_formal_batches_generated.py project/tests/test_frontend_workbench_query_contract.py project/tests/test_oneshot_terminals_api.py project/tests/test_display_lookup_status_api.py project/tests/test_detector_result_clues_api.py project/tests/test_detector_result_runs_api.py project/tests/test_report_context_observation_date_api.py project/tests/test_observation_context_2025_12_05.py`
  - Result: 43 passed, 1 warning.
- `python -m py_compile ...`
  - Result: passed.
- `git diff --check`
  - Result: passed, with line-ending warnings only.

Live API on port 18080:

- `GET /api/v1/my/manufacturers`: 200, 10 manufacturers.
- `GET /api/v1/display-lookup/status`: 200, ready.
- `GET /api/v1/daily-detector/status`: 200 for 2025-12-01 and 2025-12-05.
- `GET /api/v1/daily-detector/clues`: 200 for 2025-12-01 and 2025-12-05.
- `GET /api/v1/workbench`: 200 for 2025-12-01 and 2025-12-05, strict single-manufacturer scope.
- `GET /api/v1/oneshot-terminals`: 200 for 2025-12-01 and 2025-12-05.

Frontend build:

- Not run. This round did not modify frontend source code.

## Final Checklist

[x] 正式结果目录不再包含正式 CSV

[x] manifest 强制 data_backend=parquet

[x] Parquet 写入失败不会回退 CSV

[x] 正式 reader 不会读取 CSV

[x] Display Lookup 可独立刷新且不会执行模型评分

[x] Registry 可独立重建且不会执行模型或 detector

[x] Daily Detector 已实现独立运行，或已明确 detector input snapshot blocker

Status: blocker explicitly confirmed: `DETECTOR_INPUT_SNAPSHOT_MISSING`.

[x] 本轮没有重新执行历史月份模型预测

[x] 当前月度概率、风险对象、排序和 artifact ID 未被意外改变

[x] 已输出下一阶段前端查询重构契约
