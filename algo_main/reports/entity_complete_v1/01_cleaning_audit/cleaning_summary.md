# Cleaning Summary

- clean rows: 693596
- model_base rows: 693596
- audit rows: 693596
- manufacturer count: 13
- hospital count: 33287
- drug count: 47
- entity count: 51536
- purchase_time range: 2010-04-26 to 2026-06-24
- key null rates: {'manufacturer_code': 0.0, 'hospital_code': 0.0, 'drug_code': 0.0, 'purchase_time': 0.0, 'order_detail_id': 0.0}
- status mapping audit rows: 4907

Order status does not negate a purchase event in v1. `drug_category_code` is retained as a category code, not a product-line code. Enterprise code remains excluded from algorithm features.
