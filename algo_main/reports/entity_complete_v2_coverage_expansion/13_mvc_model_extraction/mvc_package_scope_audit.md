# MVC Package Scope Audit

The existing `10_mvc_model_package` output is retained as an internal/debug artifact only.

- current RiskEntity rows: 393377
- current RiskCard rows: 1004331
- current Evidence rows: 610954
- likely source tables: full M5 candidate_status_decision plus broad M4/M7 row-level outputs.
- exceeds frontend worklist scale: true
- visibility: internal_only
- not_for_frontend_default: true

Frontend pages must use `10_frontend_worklist_model_package`, not the broad internal dump.
