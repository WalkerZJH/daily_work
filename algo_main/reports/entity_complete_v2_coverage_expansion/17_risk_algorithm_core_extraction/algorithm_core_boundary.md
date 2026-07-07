# Algorithm Core Boundary

`risk_algorithm_core` is the production monthly algorithm runtime.

It owns:

- raw input batch reading;
- schema mapping;
- normalization;
- monthly cutoff and entity construction;
- feature engineering;
- stable model artifact scoring;
- bounded worklist candidate selection;
- detector quality gates and detector execution;
- status decision;
- RiskEntity / RiskCard / Evidence batch assembly.

It does not own:

- research training;
- hyperparameter tuning;
- SQL extraction experiments;
- M1/M3/M4/M5/M7 research outputs;
- backend API routing;
- frontend rendering;
- PDF generation.

`risk_model_core` remains the result-reading MVC Model layer. It must not read raw business tables or database sources.
