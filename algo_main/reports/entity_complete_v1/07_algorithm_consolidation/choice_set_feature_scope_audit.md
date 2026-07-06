# Choice-Set Feature Scope Audit

| feature_name                                        | runtime_feature_scope    | available   |
|:----------------------------------------------------|:-------------------------|:------------|
| hospital_drug_order_count_asof_cutoff               | partial_platform_context | True        |
| hospital_drug_active_manufacturer_count_asof_cutoff | partial_platform_context | True        |
| hospital_drug_order_count_last_12m_asof_cutoff      | partial_platform_context | True        |
| hospital_drug_order_count_last_3m_asof_cutoff       | partial_platform_context | True        |
| manufacturer_share_within_hospital_drug_asof_cutoff | partial_platform_context | True        |
| competitor_order_count_asof_cutoff                  | partial_platform_context | True        |
| competitor_order_count_last_12m_asof_cutoff         | partial_platform_context | True        |
| competitor_order_count_last_3m_asof_cutoff          | partial_platform_context | True        |
| manufacturer_substitution_context_available         | partial_platform_context | True        |
| manufacturer_share_within_hospital_drug_asof_cutoff | partial_platform_context | True        |
| competitor_order_count_last_12m_asof_cutoff         | partial_platform_context | True        |
| competitor_order_count_last_3m_asof_cutoff          | partial_platform_context | True        |

These fields are built as-of cutoff, so they are not marked as future leakage. They are still not customer-facing causal explanations: the extract only covers selected manufacturers/entities/hospital-drug pairs and cannot be described as full market share, confirmed competitor substitution, or hospital intent.
