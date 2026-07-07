# Future Algorithm Plugin Plan

`algo_main` remains the place for research and experimentation.

When a future algorithm component is promoted:

1. export a stable model artifact or detector rule spec;
2. add a small production adapter in `risk_algorithm_core`;
3. keep feature schema and artifact manifest explicit;
4. add contract tests;
5. keep `risk_model_core` unchanged unless result-batch schema changes.

Plugin candidates:

- replacement main churn artifact;
- calibrated probability artifact;
- additional safe detector;
- product-line-aware grouping after business mapping is approved;
- ClickHouse raw table reader.
