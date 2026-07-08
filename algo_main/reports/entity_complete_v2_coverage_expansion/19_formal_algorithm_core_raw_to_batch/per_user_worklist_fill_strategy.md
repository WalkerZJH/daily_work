# Per-User Worklist Fill Strategy

- business requirement: provide 20 to 50 monthly review items per user, not 20 to 50 globally.
- current user scope column: not available in this batch.
- offline fill scope used for audit: `manufacturer_code`.
- configured minimum per user: 20
- configured maximum per user: 50
- users in current formal batch: 10
- users below minimum after safe fill: 0

## Fill Order

1. Recurring risk candidates ranked by formal artifact probability and relative value.
2. New-terminal / one-shot attention candidates, kept separate from recurring churn.
3. Observation candidates for intermittent or lumpy demand, marked as observation only.
4. If a user still has fewer than 20 safe candidates, the shortage is reported; the runtime does not fabricate candidates and does not mark observation fill as high risk.

## Current Constraint

The current raw input batch does not include a stable business-owner or salesperson routing table.
Therefore `manufacturer_code` is used as the offline worklist user scope. Once `org_scope`
is available, set `worklist_user_key` to the owner/user field and rerun without changing
the frontend or model-core contracts.

This means the current formal algorithm batch can prove the per-scope fill logic
shape, but it cannot prove true per-user 20 to 50 delivery until `org_scope`
or an equivalent user routing table is provided.
