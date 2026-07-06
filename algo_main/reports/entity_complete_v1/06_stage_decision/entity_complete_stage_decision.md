# Entity Complete Stage Decision

1. New data is entity-complete for selected manufacturers and sampled entity keys; it is not full SQL-universe complete.
2. Hospital-drug choice-set context is added so manufacturer switching is not automatically treated as terminal demand loss.
3. Old metrics are considered contaminated by the row-level TOP N extract and must not be used as service conclusions.
4. New main model full-universe AUC: 0.8212
5. Mean M1 candidate die recall: 0.1862
6. M2 one-shot remains separate from recurring churn.
7. M3/M4/M5/M7 passed light semantic checks as evidence/review layers, not probability services.
8. Frontend/backend design allowed: internal diagnostic view only
9. Customer-facing probability service: no.
10. Static proof-case report: allowed for internal analysis.
11. Next algorithm task: expand entity/manufacturer/choice-set complete coverage or run confirmed time-window-complete extraction before customer-facing service.
