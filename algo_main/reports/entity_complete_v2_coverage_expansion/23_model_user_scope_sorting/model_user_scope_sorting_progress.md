# Model User Scope Sorting Progress

- started: clarify model-core sorting boundary for backend-resolved user scopes.
- red test: `pytest -q tests/test_risk_model_core_rankable_entities.py` failed because `list_rankable_entities` did not exist.
- implementation: added repository/service helper that filters by backend-provided `manufacturer_codes` and returns count metadata without filling.
- green test: `pytest -q tests/test_risk_model_core_rankable_entities.py` passed.

