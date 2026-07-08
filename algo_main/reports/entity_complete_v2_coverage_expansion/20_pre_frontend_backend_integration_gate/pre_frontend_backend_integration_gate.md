# Pre Frontend Backend Integration Gate

- formal_frontend_backend_integration_ready: CONDITIONAL_READY
- integration_start_allowed: YES_FOR_CORE_RISK_PAGES
- based_on_working_tree: true
- project_wip_present: true
- frontend_wip_present: true
- project_frontend_wip_unchanged: True
- backend API integration can start: yes, for core risk pages
- frontend mock replacement can start: yes, for core risk pages
- first pages: index/workbench, clues/risk list, clue-detail/risk cards, dashboard/monthly
- deferred pages: proof-case/backtest, verify/recovery, distributor alerts, order detail, PDF export
- blockers: none for core risk pages

The current algorithm/data layer is `CONDITIONAL_READY`, not full `READY`,
because strict SQL/raw-orders-to-fact parity and org/user routing remain later
gates. Result-batch differences are formal algorithm batch vs frontend
projection differences, not model/feature/candidate semantic blockers.

| gate                                      | status            |
|:------------------------------------------|:------------------|
| source_of_truth_ready                     | CONDITIONAL_READY |
| risk_algorithm_core_ready                 | CONDITIONAL_READY |
| raw_to_feature_parity_ready               | READY             |
| best_model_artifact_ready                 | READY             |
| monthly_runner_ready                      | READY             |
| result_batch_contract_ready               | READY             |
| risk_model_core_ready                     | READY             |
| backend_api_contract_ready                | CONDITIONAL_READY |
| frontend_payload_contract_ready           | CONDITIONAL_READY |
| customer_visibility_safe                  | READY             |
| detector_business_boundary_ready          | CONDITIONAL_READY |
| proof_case_ready                          | CONDITIONAL_READY |
| work_order_ready                          | CONDITIONAL_READY |
| export_ready                              | CONDITIONAL_READY |
| formal_frontend_backend_integration_ready | CONDITIONAL_READY |
