# Full Result-Batch Parity Report

The formal runtime output is a monthly algorithm batch. The current v2 frontend
worklist package is a narrower projection. This report therefore checks whether
same-scope frontend reference rows are covered, and keeps row-count differences
as projection warnings rather than feature/model blockers.

| metric                                            | status   |   production_value |   reference_value | blocker_reason                                                                                                    |
|:--------------------------------------------------|:---------|-------------------:|------------------:|:------------------------------------------------------------------------------------------------------------------|
| reference_full_rows                               | info     |               1291 |               871 | reference batch contains 871 multi-cutoff/multi-horizon rows; filtered to cutoff=2025-12-31, horizon=H6           |
| reference_scope_rows                              | pass     |               1291 |                12 |                                                                                                                   |
| risk_entities_row_count                           | warn     |               1291 |                12 | formal algorithm batch is broader than current frontend projection; frontend_worklist_projection remains separate |
| selected_entity_key_overlap                       | pass     |                 12 |                12 |                                                                                                                   |
| risk_cards_row_count                              | warn     |               4197 |                38 | formal algorithm batch cards cover broader M1 worklist than current frontend projection                           |
| evidence_row_count                                | warn     |               4197 |                26 | formal algorithm batch evidence covers broader M1 worklist than current frontend projection                       |
| auto_dispatch_allowed_count                       | pass     |                  0 |                 0 |                                                                                                                   |
| customer_facing_probability_service_allowed_count | pass     |                  0 |                 0 |                                                                                                                   |
