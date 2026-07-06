# Probability Service Gate Decision

## Internal Diagnostic View

Allowed: true

Reason: leakage audit has no blocking feature in strict probability model sets, and the model is useful for algorithm analysis.

## Analyst View / Proof-Case Report

Allowed: true

Reason: full-universe strict test metrics are strong enough for analyst review if caveats are shown.

## Customer-Facing Probability Service

Allowed: false

Blocking constraints if false: selected_subset_not_full_sql_universe, probability_availability_gate_not_implemented_as_runtime_policy, partial_platform_choice_set_features_not_customer_claim_safe, manual_review_load_requires_product_threshold
