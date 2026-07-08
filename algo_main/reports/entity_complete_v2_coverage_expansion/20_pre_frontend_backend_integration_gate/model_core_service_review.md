# Model Core Service Review

- gate: READY
- backend can depend on risk_model_core only: true
- algo_main import required: false
- M closure direct reads required: false
- training files required: false
- M1/M3/M4/M5/M7 knowledge required by backend: false

| check                            | value                                                                 |
|:---------------------------------|:----------------------------------------------------------------------|
| import_risk_model_core           | True                                                                  |
| manifest_batch_id                | 2025-12-monthly-risk-algorithm-formal-v2-raw                          |
| risk_entities_rows               | 1291                                                                  |
| first_entity_id                  | 43B3F24E6895475BA3EA1CD00FA74CE0|YLNS00448038|ZA04CBH0205010303704|H3 |
| risk_cards_rows_for_first_entity | 4                                                                     |
| evidence_rows_for_first_card     | 1                                                                     |
| timeline_rows_for_first_entity   | 1                                                                     |
| hospital_aggregates_rows         | 612                                                                   |
| drug_aggregates_rows             | 32                                                                    |
| monthly_reports_rows             | 1                                                                     |
| proof_cases_rows                 | 0                                                                     |
| risk_query_detail_available      | True                                                                  |
| risk_card_service_copy_rows      | 4                                                                     |
| page_payload_status              | present_or_fallback                                                   |
| page_payload_error               |                                                                       |
| forbidden_claims_check           | True                                                                  |
| forbidden_claims_error           |                                                                       |
