# Production Feature Contract

Production runtime derives features from raw orders/master tables, then aligns the model frame to feature_schema.json. Missing columns are only filled when feature_schema declares a default; otherwise formal run fails.
