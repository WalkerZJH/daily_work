# Detector Catalog

Categories:

- `price_warning`
- `delivery_response`
- `terminal_change`
- `sales_fluctuation`
- `common_preprocess`

Current implemented terminal-change detectors:

- `inactive_terminal`
- `new_terminal`
- `ip_interval`
- `frequency_drop`
- `sku_shrink`
- `substitution_risk`
- `cycle_deviation`

Price-warning detectors:

- `low_price`: implemented v1 threshold rule. If no `warning_price` config exists, it does not trigger and emits `LOW_PRICE_THRESHOLD_NOT_CONFIGURED`.
- `price_spread`: implemented v1 recent-window max/min comparable unit price spread rule. Default ratio threshold is `1.8`.

Delivery-response detectors:

- `delivery_refusal`: implemented v1 keyword rule on `order_status`.
- `delivery_delay`: placeholder; current data only supports `delivery_time - order_time` approximation.
- `low_delivery_rate`: placeholder in catalog; a lightweight order-level rule can be enabled later.

Detector output is normalized into `DetectorEvidence`. Risk cards aggregate evidence families without weighted severity averaging. `P(alive)` fields are present but null until a calibrated backbone model is implemented.
