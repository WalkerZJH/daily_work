# Model User Scope Sorting Contract

## Boundary

`risk_model_core` does not own real user permission resolution. The backend
resolves a user through `org_scope`, salesperson assignment, regional-manager
routing, or equivalent business rules, then passes the visible
`manufacturer_codes` into model-core query methods.

Model-core may filter, sort, and return stable result-batch fields. It must not
treat `manufacturer_code` as a user identifier and must not force a fixed
workbench size.

## Runtime Contract

Backend call shape:

```python
RiskQueryService(repo).list_rankable_entities(
    manufacturer_codes=["M001", "M002"],
    report_month="2025-12",
    horizon="H6",
    candidate_type="recurring",
    sort_by=["business_priority_score", "risk_score_display"],
    limit=50,
    target_min=20,
)
```

Returned metadata:

- `items`: result-batch rows with rankable fields preserved.
- `available_count`: rows available under the backend-resolved manufacturer set.
- `returned_count`: rows returned after `limit`.
- `shortage_count`: `max(target_min - returned_count, 0)` when `target_min` is provided.
- `scope.manufacturer_code_is_user_scope`: always `False`.
- `scope.scope_resolved_by_backend`: `True`.

## Sorting Fields

The helper preserves all columns from `risk_entities`. If present, backend can
sort or consume:

- `risk_probability_value`
- `risk_score_display`
- `business_priority_score`
- `value_at_risk_proxy`
- `recent_order_amount`
- `avg_order_amount`
- `purchase_interval_overdue_score`
- `purchase_frequency_drop_score`
- `final_candidate_status`
- `risk_level`
- `review_priority`
- `evidence_strength`

The current formal batch contains `risk_score_display` and
`risk_probability_value`; numeric amount/value proxies are not yet verified in
the result batch, so backend must not fabricate business value.

## Non-Responsibilities

Model-core does not:

- resolve user, role, region, or salesperson permissions;
- assume one user equals one `manufacturer_code`;
- enforce a backend workbench-size policy;
- choose whether to fill shortage with observation or one-shot rows;
- create work orders;
- dispatch tasks;
- recalculate model scores or detector evidence;
- import `algo_main`;
- expose result batch directly to the frontend.

## Current Readiness

This update makes model-core ready for backend-resolved user scopes across
multiple manufacturers. True per-user workbench delivery remains a backend policy
that depends on `org_scope` or equivalent routing data.
