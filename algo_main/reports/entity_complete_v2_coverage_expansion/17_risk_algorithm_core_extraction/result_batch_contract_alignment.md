# Result Batch Contract Alignment

`risk_algorithm_core` writes monthly `risk_result_batch`.

Validation chain:

1. `risk_result_contracts.validate_result_batch`
2. `risk_model_core.validation.validate_batch`
3. `risk_model_core.repositories.ParquetRiskResultRepository`

Required monthly table:

- `monthly_reports`

No non-monthly report table alias is part of the contract.

The fixture run confirms the output batch can be loaded by `risk_model_core`.
