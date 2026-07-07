# Independence Check Report

Command:

```powershell
python scripts\check_risk_algorithm_core_monthly_run.py --clean-output
```

Result: passed.

Observed output:

```text
monthly_run_check: ok
report_month: 2026-07
cutoff_date: 2026-07-31
entity_rows: 21
feature_rows: 21
score_rows: 21
selected_candidate_rows: 21
risk_entities: 21
risk_cards: 69
```

Independence claims:

- runs from repository root;
- does not insert `algo_main/src`;
- imports `risk_algorithm_core`, `risk_result_contracts`, and `risk_model_core`;
- does not import M closure modules;
- writes a monthly result batch readable by `risk_model_core`.
