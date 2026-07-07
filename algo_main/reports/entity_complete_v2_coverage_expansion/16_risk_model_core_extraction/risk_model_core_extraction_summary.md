# Risk Model Core Extraction Summary

This stage extracts a root-level `risk_model_core` package from the algorithm-side MVC adapter prototype.

Result:

- `risk_model_core` is importable from repository root.
- It does not import `alg.*` or `algo_main.*`.
- It reads only standard `risk_result_batch` tables and payload JSON.
- It provides manifest validation, domain objects, repository interfaces, services, safe business copy rendering, page payload access, export contract, and validation helpers.
- It keeps ClickHouse integration as a repository stub.

Non-goals:

- no model training;
- no SQL extraction;
- no feature engineering;
- no M closure computation;
- no frontend/backend API implementation;
- no formal PDF generation.

Business cadence: monthly report is the fixed delivery interval. Daily naming is not product semantics.

