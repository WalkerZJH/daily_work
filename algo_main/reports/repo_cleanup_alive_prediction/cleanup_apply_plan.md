# Cleanup Apply Plan

This stage is dry-run only. Do not delete files.

If an apply mode is used later, it must be invoked as:

```bash
python scripts/audit_alive_prediction_repo_cleanup.py --apply --confirm
```

Apply mode may only move manually reviewed candidates to `_archive/`; it must not remove data/cache/parquet/reports.

Recommended canonical locations:
- metrics: `src/alg/metrics/`
- calibration: `src/alg/metrics/calibration.py` or `src/alg/validation/`
- temporal split: `src/alg/validation/`
- feature set definitions: `src/alg/features/`
- presentation/report helpers: `src/alg/evaluation/`
- path helpers: `src/alg/artifacts/paths.py` or `src/alg/utils/`