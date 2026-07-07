# Feature Engineering Contract

`risk_algorithm_core` builds production features internally from raw orders.

Implemented feature groups:

- recency;
- frequency;
- interval;
- quantity;
- value proxy;
- demand shape;
- history sufficiency;
- one-shot attention.

Rules:

- features are as-of cutoff;
- cutoff is month end;
- cutoff-after data is not used;
- training labels are not produced for production scoring;
- product line mapping is display metadata unless entity grain is explicitly changed later.
