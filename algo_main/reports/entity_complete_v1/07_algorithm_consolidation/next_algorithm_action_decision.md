# Next Algorithm Action Decision

1. Current metrics credible: true with strict split caveats.
2. Blocking leakage: false.
3. Re-cleaning needed: false.
4. New data needed: true, for broader manufacturer/time-window coverage before customer-facing probability.
5. Model change needed: no immediate replacement; keep XGBoost as main candidate and logistic as transparent fallback.
6. Continue XGBoost tuning: only light targeted tuning, not broad blind search.
7. Keep logistic: true, as fallback/benchmark.
8. Keep interval evidence: true, as evidence/ranking support, not calibrated probability.
9. M1 candidate policy v2 required: true; recommended policy is `multi_recall_union_top10`.
10. Internal diagnostic view allowed: true.
11. Analyst view allowed: true.
12. Proof-case report allowed: true.
13. Customer-facing probability service allowed: false.
14. Next best task: expand complete coverage and implement probability availability gates before productizing probabilities.
