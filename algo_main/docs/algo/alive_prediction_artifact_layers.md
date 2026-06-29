# Alive Prediction Artifact Layers

`data/cache/` is only a temporary acceleration layer. It is not the semantic
entry point for training or prediction.

Stable alive prediction data layers:

- `data/04_facts/alive_prediction/`: stable facts such as
  `fact_purchase_event__drug_code.parquet` and
  `fact_entity_month__drug_code.parquet`. These facts do not include cutoff
  range, horizon, candidate policy, or status-history flags in their filenames.
- `data/05_features/alive_prediction/`: cutoff-dependent candidate sets,
  demand profiles, labels, and feature tables.
- `data/06_train_sets/alive_prediction/`: explicit train/eval/diagnostic sets
  after scope filtering and trainability checks.
- `data/07_outputs/alive_prediction/`: machine-readable outputs and reports.

Legacy cache migration is reuse-first:

```powershell
$env:PYTHONPATH='src'
python scripts\migrate_alive_prediction_cache.py --dry-run
```

The migration script defaults to dry-run and copy planning. It does not delete
legacy cache files. Actual copy requires `--confirm --no-dry-run`; move requires
both `--mode move` and `--confirm --no-dry-run`.

Materialization also uses a reuse-first policy:

1. Reuse existing `data/04_facts`, `data/05_features`, or `data/06_train_sets`
   artifacts when metadata matches.
2. If a stable artifact is missing, look for a compatible legacy cache file and
   copy it into the stable data layer.
3. Rebuild only when no reusable artifact exists, and never silently overwrite.

Cleanup is restricted to `data/cache/alive_prediction/tmp/` and defaults to
dry-run:

```powershell
$env:PYTHONPATH='src'
python scripts\clean_alive_prediction_cache.py --dry-run
```

Ignored parquet/cache files are still valuable local work products. Do not
delete `data/03_cleaned`, `data/04_facts`, `data/05_features`, `data/06_train_sets`,
or `data/cache/alive_prediction_sanity` artifacts unless a user explicitly asks
for that exact deletion and the cleanup guard confirms the target is allowed.
