# Import Dependency Audit

`risk_model_core` is a root-level package. It is designed to be imported without adding `algo_main/src` to `sys.path`.

Allowed dependencies:

- Python standard library
- pandas

Disallowed dependencies:

- `alg.*`
- `algo_main.*`
- entity_complete training or M-stage modules
- xgboost / lightgbm / catboost / sklearn
- SQL extraction or feature engineering code

The independence test imports `risk_model_core` directly from the repository root and checks that no loaded module starts with `alg.tasks.die_prediction`.

