# Model Artifact Contract

Default artifact path:

`model_artifacts/risk_algorithm_core/main_churn/current/`

Required files:

- `artifact_manifest.json`
- `model.joblib`, `model.pkl`, or `model_stub.json` for tests
- `feature_schema.json`

Formal run behavior:

- if the artifact manifest or model file is missing, formal run fails;
- no silent fallback to rule baseline is allowed;
- dry-run may use `RuleBaselineScorer`;
- dry-run output must not be called a formal production model result.

Fixture artifact:

`tests/fixtures/model_artifacts/risk_algorithm_core/main_churn/current/`

The fixture uses `linear_stub` only for contract tests.
