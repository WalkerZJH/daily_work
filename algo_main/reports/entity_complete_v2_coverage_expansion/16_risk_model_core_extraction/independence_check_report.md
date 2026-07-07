# Independence Check Report

Command run:

```powershell
python scripts\check_risk_model_core_independence.py --batch-dir tests\fixtures\risk_result_batch_minimal
```

Result: passed.

Key checks:

- `risk_model_core` imports from repository root.
- The script does not insert `algo_main/src` into `sys.path`.
- The package loads only the standard `risk_result_batch` fixture.
- The fixture uses explicit monthly report naming: `monthly_reports.csv`, `MonthlyReport`, and `list_monthly_reports`.
- The fixture does not contain non-monthly compatibility report interface names.
- Repository, service, page payload builder, and business copy renderer can run from the standard batch.
- `auto_dispatch_allowed=false`.
- `customer_facing_probability_service_allowed=false`.

Observed script output:

```text
batch_id: fixture-monthly-v1
report_month: 2025-12
risk_entities_head: [{'risk_entity_id': 're_1', 'candidate_id': 'c1'}, {'risk_entity_id': 're_2', 'candidate_id': 'c2'}]
first_detail_cards: 1
index_payload_keys: ['hero', 'page_title', 'top_clues']
clues_items: 2
watchlist_items: 1
independence_check: ok
```
