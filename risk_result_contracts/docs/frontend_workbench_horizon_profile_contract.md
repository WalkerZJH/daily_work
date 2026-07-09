# Frontend Workbench Horizon Profile Contract

## Scope

The serving chain is:

```text
risk_algorithm_core -> risk_result_batch -> risk_model_core -> project API -> front_end
```

`risk_model_core` reads result-batch or future result-serving tables only. It does not read raw orders, source business databases, user permissions, `top_n` page controls, or `algo_main` static files.

## Horizon Profiles

Monthly result batches with schema `risk_result_batch_monthly_v2` must include:

```text
risk_entity_horizon_profiles
```

Required key:

```text
risk_entity_id, report_month, horizon
```

Required serving fields:

```text
risk_probability
involved_amount
involved_amount_source
risk_level
risk_band
main_reason_summary
reason
detector_evidence_count
updated_at
```

`H3`, `H6`, and `H12` switching must use rows from this table. The page builder must not synthesize three horizons by copying one `risk_entities` row.

## Involved Amount

`involved_amount` means selected horizon window consumption.

For the current monthly batch, the source fields are:

```text
H3  -> purchase_amount_sum_last_3m_asof_cutoff
H6  -> purchase_amount_sum_last_6m_asof_cutoff
H12 -> purchase_amount_sum_last_12m_asof_cutoff
```

It must not use all-history amount, total lifetime amount, or an overall consumption total.

## Loss Value Fields

Customer-facing frontend payloads do not need to display `loss_value`, `monthly_loss_value`, or `business_score`.

Those fields may remain in internal detector/result compatibility contracts, especially:

```text
daily_detector_clues.monthly_loss_value
```

They are internal or deprecated for customer pages and should not be required by frontend workbench payloads.

## Detector Semantics

Detector tables remain read-only result-batch tables:

```text
detector_catalog
daily_detector_runs
daily_detector_clues
high_risk_detector_evidence
```

`detector_score` is a rule inspection score. It is not a churn probability, not a model probability, and not a replacement for monthly `risk_probability`.

## Layer Boundaries

Model/result-batch layers do not resolve:

```text
current_user
manufacturer permissions
top_n
page dropdown dates
frontend sorting UI
```

Those policies belong to `project` API and frontend integration layers.
