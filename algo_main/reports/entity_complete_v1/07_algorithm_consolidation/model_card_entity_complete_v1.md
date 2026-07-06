# Model Card Entity Complete V1

- data version: entity_complete_v1
- row count: 3551706
- entity count: 45774
- selected manufacturers shown: 1D93E15EBB9B4F14A1C18E0CD1750A0A, 263F9947B4FA4F8DB61C9FF48D5A942A, 9701EFF559DF4862AF18CF0DC1B6962D, C458C50660B24C6B96A91FEBAAE8E5C8, DFC52F4CCF384D849D053242EA2935F3, E50FC20840554CF79ACAEF2582AE63BD, F9BDA11C2EE443F49615B9AD6AFBD4AA, eb0bd11ce688dc0dead47b46ce866027
- cutoff range: 2020-01-31 to 2025-12-31
- label definition: fixed-window die label, `label_die_H=1` if no purchase exists in `(cutoff, cutoff + H]`.
- feature groups: recency/frequency, interval, demand shape, manufacturer/hospital/drug context, order-status evidence, and as-of partial choice-set context.
- excluded probability features: value/business priority, detector severity, raw non-asof date fields, labels, and candidate policy fields.
- leakage conclusion: blocking leakage = False
- selected model family: XGBoost small, in-memory only.
- validation split: horizon-specific time split with purge gap; no random K-fold primary validation.
- selected strict test AUC / PR-AUC gain / ECE: 0.8182 / 0.3322 / 0.0300
- calibration: raw_preferred_by_validation_proxy
- candidate policy status: multi_recall_union_top10, recall 0.4452
- probability availability scope: internal/analyst only; customer-facing service is not approved.

## Forbidden Interpretations

- The hospital has certainly churned.
- The hospital intentionally abandoned a manufacturer.
- Other manufacturers definitely replaced this product.
- The choice-set fields represent complete market share.
- Low risk means safe.
- Business priority is probability.
