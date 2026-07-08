# Source-of-Truth Readiness Review

- gate: CONDITIONAL_READY
- source flow map exists: True
- source flow map csv exists: True
- raw/fact source confirmed: true; current formal mode is normalized_fact_mode
- feature generation source confirmed: true
- best model artifact confirmed: true
- candidate policy confirmed: true; formal batch is broader than frontend projection
- detector/status/evidence flow confirmed: true for integration gate scope
- approximate feature builder remains in formal path: false
- parity-loosening risk: no raw-to-feature warning remains; result differences are projection/worklist scope warnings

Current second layer is `CONDITIONAL_READY`: it proves
`fact_entity_month -> feature -> artifact score -> monthly risk_result_batch`.
Strict SQL/raw-orders-to-fact parity remains a later production gate.
