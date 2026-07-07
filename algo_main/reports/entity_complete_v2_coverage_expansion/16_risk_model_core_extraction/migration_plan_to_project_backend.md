# Migration Plan To Project Backend

`risk_model_core` is now the candidate MVC Model layer for backend integration.

Migration direction:

1. Keep `algo_main` responsible for algorithm research and batch production.
2. Keep `algo_main/src/alg/tasks/die_prediction/mvc_model_package/` as the algorithm-side adapter that produces standard result batches.
3. Move or vendor `risk_model_core/` into backend code only after API boundaries are finalized.
4. Backend APIs should depend on `risk_model_core` repositories and services, not on M1/M3/M4/M5/M7 source tables.
5. Frontend pages should consume backend APIs that are backed by `risk_model_core`, not algorithm experiment outputs.
6. ClickHouse integration should replace only `RiskResultRepository`, leaving services and page payload logic stable.

Monthly cadence requirement:

- Business delivery cadence is monthly.
- Backend API naming should use monthly semantics, such as `/api/monthly-reports`.
- Domain naming should use `MonthlyReport`.
- Storage naming should use `monthly_reports`.
- Do not keep daily report aliases for compatibility in the Model contract.

Recommended backend split:

- `project/app/domain/risk_model/`: domain objects, enums, schemas.
- `project/app/repositories/risk_result_repository.py`: repository implementations.
- `project/app/services/risk_query_service.py`: query and page payload services.
- `project/app/services/business_copy_renderer.py`: deterministic safe copy renderer.
- `project/app/api/risk.py`: API routes, after backend implementation starts.

Not in scope for this extraction:

- FastAPI route implementation.
- Frontend changes.
- SQL extraction.
- Model training.
- Detector recomputation.
- Formal PDF generation.
