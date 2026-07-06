# Cleaning Summary

- clean rows: 827784
- model_base rows: 827784
- audit rows: 827784
- manufacturer count: 14
- hospital count: 37953
- drug count: 65
- entity count: 68877
- purchase_time range: 2010-02-23 to 2026-06-24
- key null rates: {'manufacturer_code': 0.0, 'hospital_code': 0.0, 'drug_code': 0.0, 'purchase_time': 0.0, 'order_detail_id': 0.0}
- status mapping audit rows: 5897

Order status does not negate a purchase event in v1. `drug_category_code` is retained as a category code, not a product-line code. Enterprise code remains excluded from algorithm features.
