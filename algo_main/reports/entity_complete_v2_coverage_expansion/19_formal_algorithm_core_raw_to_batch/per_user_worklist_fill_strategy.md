# Backend-Resolved User Worklist Strategy

- business requirement: provide 20 to 50 monthly review items per backend-resolved user scope, not 20 to 50 globally.
- real user scope source: `org_scope` / salesperson / regional-manager routing table in the backend.
- current user scope column: not available in this batch.
- offline audit scope used only for strategy-shape validation: `manufacturer_code`.
- configured example minimum: 20
- configured example maximum: 50
- audit scopes in current formal batch: 10
- audit scopes below example minimum after safe fill: 0

`manufacturer_code` must not be treated as a real user identifier. One user may
own multiple manufacturers, and one manufacturer may need to be routed through a
business organization table. The model layer therefore exposes rankable entities
filtered by `manufacturer_codes: list[str]`; it does not resolve permissions and
does not enforce 20-50 items.

## Fill Order

1. Backend resolves the current user's visible `manufacturer_codes`.
2. Backend asks `risk_model_core` for rankable entities inside that visibility set.
3. Model layer returns sortable fields and count metadata only.
4. Backend decides whether to show recurring only, add one-shot, add observation, or return fewer than 20.
5. If a user still has fewer than 20 safe candidates, the shortage is reported; neither model nor backend may fabricate candidates or mark observation fill as high risk.

## Current Constraint

The current raw input batch does not include a stable business-owner or salesperson routing table.
Therefore `manufacturer_code` was used only as an offline audit grouping key. Once
`org_scope` is available, the backend should map each user to a set of manufacturer
codes and pass that set to `risk_model_core` without changing the result-batch
contract.

This means the current formal algorithm batch can prove the query and fill-policy
shape, but it cannot prove true per-user 20 to 50 delivery until `org_scope` or an
equivalent user routing table is provided.
