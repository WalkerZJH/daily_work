# Monthly Run Config Contract

Config path:

`configs/risk_algorithm_core/monthly_run.example.yaml`

Cycle:

- `report_type=monthly`;
- `report_month=auto_previous_month` by default;
- `cutoff_date` resolves to the last calendar day of `report_month`;
- primary horizon defaults to H6;
- H3/H6/H12 are available.

Periodically editable fields:

- `run.report_month`;
- `run.run_date`;
- `input.raw_batch_dir`;
- scope filters;
- bounded worklist topN/load settings;
- detector enablement switches that depend on data quality.

Forbidden to expose as regular run config:

- model family selection;
- model hyperparameters;
- training parameters.

Hard safety fields:

- `auto_dispatch_allowed=false`;
- `customer_facing_probability_service_allowed=false`;
- `proof_case_report_allowed=false`.
