# Detector production boundary

This file is the operational boundary for monthly prediction and Detector production.
Read it before changing a Detector, adding a Detector, or starting a historical materialization.

## Non-negotiable separation

- Monthly prediction and Detector are separate production pipelines.
- Monthly prediction publishes only `report_month=YYYY-MM/batch_id=...` result batches.
- Detector reads raw purchase facts and publishes only `detector_run_date=YYYY-MM-DD/...` batches.
- Updating a Detector does not require rerunning monthly prediction.
- Updating monthly prediction does not require rerunning any Detector.
- Never run every Detector for every date merely because one Detector implementation or configuration changed.

The two result families meet only through the observation registry. For an observation date, the registry
associates that exact Detector date with its previous complete monthly report. Missing data must remain
missing; neither side may silently substitute another date, month, or latest batch.

## Component layout and selection

Each Detector is an immutable independently versioned component:

```text
data/project_result_batches/
  detector_run_date=YYYY-MM-DD/
    detector_id=<detector_id>/
      batch_id=YYYY-MM-DD-<run_id>/
        manifest.json
        detector_catalog.parquet
        daily_detector_runs.parquet
        daily_detector_clues.parquet
        high_risk_detector_evidence.parquet
```

`risk_model_core.repositories.CompositeDetectorResultRepository` selects the lexicographically latest
published `batch_id` independently for every `detector_id`, then presents those components as one exact-date
Detector view to Project APIs and the frontend. Publishing a new version of one Detector therefore leaves
all peer Detector selections unchanged.

Detector parameters and per-Detector versions live in
`configs/risk_algorithm_core/daily_detector_rules.yaml`. Increment the changed Detector's `version` when its
logic or output meaning changes. A new implemented Detector must have a config entry and a registered
evaluator in `risk_algorithm_core.daily_detector_runner` before production execution.

## Run only what changed

One Detector for one date:

```powershell
python -m production_pipeline.run_daily_detector `
  --raw-batch-dir <raw_batch> `
  --observation-date YYYY-MM-DD `
  --run-id <new_versioned_run_id> `
  --detector-id <detector_id>
```

One Detector for an affected date range:

```powershell
python -m production_pipeline.materialize_daily_detector_range `
  --raw-batch-dir <raw_batch> `
  --start-date YYYY-MM-DD `
  --end-date YYYY-MM-DD `
  --run-id <new_versioned_run_id> `
  --detector-id <detector_id>
```

Repeat `--detector-id` only when multiple Detectors genuinely changed. Use `--resume-existing` to resume the
same interrupted run after verifying there is no live matching process. Never overwrite a published component;
use a new `run_id`.

Monthly prediction remains a separate command:

```powershell
python -m production_pipeline.run_monthly_prediction <monthly arguments>
```

Do not append Detector execution to the monthly command and do not add monthly scoring to Detector execution.

## Migration and registry

Legacy date-wide Detector Parquet can be split without recomputation when its clue and evidence tables contain
`detector_id`:

```powershell
python -m production_pipeline.split_daily_detector_batches `
  --batch-root data/project_result_batches `
  --start-date YYYY-MM-DD `
  --end-date YYYY-MM-DD `
  --run-id <migration_run_id>
```

After publishing or splitting components, rebuild the observation registry:

```powershell
python -m production_pipeline.rebuild_observation_registry `
  --batch-root data/project_result_batches
```

Before a broad run, inspect the target date, `detector_id`, `run_id`, component directory, staging directory,
and live processes. Preserve legacy aggregate batches and failed staging evidence unless removal is explicitly
authorized. Prefer splitting existing Parquet; if recomputation is necessary, first run several dates and compare
schema, row counts, and stable business-field hashes before expanding the date range.

## Consumer verification

The live frontend path is:

```text
clues.html
  -> /api/v1/report-context
  -> /api/v1/daily-detector/status
  -> /api/v1/daily-detector/clues
  -> ReportContextService
  -> CompositeDetectorResultRepository
  -> latest component per detector_id for the exact detector_run_date
```

At minimum, verify the component repository tests, Project API tests, and one real frontend query after changing
this boundary. The page must report backend data and the selected exact observation date; demo data is not proof
that the production chain works.
