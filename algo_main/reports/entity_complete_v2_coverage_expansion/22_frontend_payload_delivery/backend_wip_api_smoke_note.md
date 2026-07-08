# Backend WIP API Smoke Note

The current `project/tests/test_frontend_pages_api.py` was run with
`RISK_RESULT_BATCH_DIR` pointing to the formal batch. The API routes returned
payloads, but three WIP assertions are intentionally not satisfied by this
model-layer delivery:

- The WIP test expects a `detector_evidence_ranker` model metric. The delivered
  payload keeps `model_metrics` empty to avoid exposing training/evaluation
  copy in customer-facing JSON.
- The WIP test expects non-empty `xgboost_shap`. The delivered detail payloads
  use `xgboost_shap: []` because the current result batch has no verified SHAP
  or feature contribution table.
- The WIP test expects `expected_repurchase_amount > 0`. The delivered oneshot
  payload uses `0` because the current result batch has no numeric first
  purchase amount or expected repurchase amount source column.

These are backend/frontend WIP expectation differences, not schema validation
failures. The generated payloads validate against
`project/app/schemas/frontend_pages.py`.
