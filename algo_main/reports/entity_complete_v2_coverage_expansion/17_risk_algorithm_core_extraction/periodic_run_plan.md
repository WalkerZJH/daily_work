# Periodic Monthly Run Plan

Default schedule:

- run after a full natural month closes;
- if run on 2026-08-05, default `report_month=2026-07`;
- default `cutoff_date=2026-07-31`.

Operator inputs:

- raw batch directory;
- optional schema mapping path;
- report month override;
- scope filters;
- bounded worklist capacity.

Execution:

```powershell
python -m risk_algorithm_core.cli run --config configs/risk_algorithm_core/monthly_run.example.yaml
```

Dry-run:

```powershell
python -m risk_algorithm_core.cli dry-run --config configs/risk_algorithm_core/monthly_run.example.yaml --use-rule-baseline
```

Consumer:

- backend should read the generated `risk_result_batch` through `risk_model_core`;
- frontend should consume backend APIs, not raw algorithm tables.

Forbidden config changes:

- enabling auto dispatch;
- enabling customer-facing probability service;
- swapping model family or hyperparameters in run config.
