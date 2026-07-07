# MVC Model Package to Risk Model Core Boundary

`algo_main/src/alg/tasks/die_prediction/mvc_model_package/` is an algorithm-side adapter and batch producer. It may read M closure outputs, service gates, detector gates, and entity_complete artifacts.

`risk_model_core/` is the independent MVC Model layer candidate. It does not import `alg.*`, does not read M closure tables, and only consumes standard `risk_result_batch` inputs.

Backend code should not import `alg.tasks.die_prediction.mvc_model_package`. Backend API and repository code should consume `risk_model_core` and a stable result batch.

Objects owned by `risk_model_core`:

- RiskEntity
- RiskCard
- RiskEvidence
- RiskTimelinePoint
- HospitalAggregate
- DrugAggregate
- MonthlyReport rows
- ProofCase
- WorkOrderReserved

Dependencies that must stay in `algo_main`:

- SQL extraction
- cleaning and feature build
- model training
- M1/M3/M4/M5/M7/M8 generation
- detector enablement batch production
- entity_complete_v1/v2 research paths

Design cadence note: business delivery is monthly. `risk_model_core` standard interfaces use `MonthlyReport` / `monthly_reports` only; non-monthly report naming is not part of the core contract.
