# M4 Detector Catalog 审计

## 状态

新链路为 `partially_implemented`；旧链路有较完整 detector 原型；price/delivery/SKU/wallet share 多数是 interface-only 或 deferred。

## 当前 entity_complete_v1 证据

`m4_detector_evidence_metrics.csv` 当前只有两个 aggregate detector evidence：

- `frequency_drop_detector_hit`
- `interval_overdue_detector_hit`

二者都明确为 evidence，不是 probability。

当前没有生成 row-level `detector_evidence_results`，没有统一 detector schema、evidence_id/hash、evidence_values、data_quality_status 等完整字段。

## legacy detector 状态

旧链路 `alive_prediction_detectors_v1`：

- `terminal_loss_warning`：implemented，hit 183
- `new_terminal_detection`：implemented，hit 564
- `purchase_frequency_fluctuation_warning`：implemented，hit 550
- `purchase_quantity_fluctuation_warning`：implemented，hit 811
- `low_price_purchase_warning`：interface_only
- `order_price_spread_warning`：interface_only
- `rejection_response_warning`：interface_only
- `delayed_response_warning`：interface_only
- `low_delivery_rate_warning`：interface_only

旧链路 `alive_prediction_detectors_v2`：

- `purchase_interval_overdue_warning`：implemented，hit 183
- `purchase_frequency_decay_rate_test`：implemented，hit 86，p_value_available_count 1,354

## 逐 detector 结论

| detector | status | 说明 |
|---|---|---|
| terminal_loss_warning | implemented_legacy_only | 新链路只有 interval aggregate，未重跑 row-level detector |
| new_terminal_detection | implemented_legacy_only | 新链路 one-shot features 有，但 detector 未重跑 |
| purchase_interval_overdue_warning | partially_implemented | 新链路有 interval_overdue hit aggregate，legacy 有完整 row-level |
| purchase_frequency_fluctuation_warning | partially_implemented | 新链路有 frequency_drop aggregate，legacy 有完整 row-level |
| purchase_frequency_decay_rate_test | implemented_legacy_only | 新链路未重跑 p-value/fdr-ready detector |
| purchase_quantity_fluctuation_warning | implemented_legacy_only | legacy implemented，新链路未重跑 |
| purchase_quantity_trend_warning | intentionally_deferred | design_first，需要 numeric reliability guardrail |
| purchase_amount_trend_warning | interface_only | 金额为相对/脱敏语义，不能直接解释 |
| sku_narrowing_warning | intentionally_deferred | 缺 product_line / portfolio mapping |
| wallet_share_decline_warning | intentionally_deferred | choice-set 只是 partial context，不是完整市场份额 |
| low_price_purchase_warning | interface_only | 价格可比口径不足 |
| order_price_spread_warning | interface_only | 价格单位、规格、可比价未确认 |
| rejection_response_warning | interface_only | 旧链路保留接口 |
| delayed_response_warning | intentionally_deferred | delivery_time / arrival_time 缺失或不稳定 |
| low_delivery_rate_warning | intentionally_deferred | 当前阶段跳过，弱规则未启用 |

## 结论

M4 不能算在新链路完整完成。P1 应优先把 interval overdue 与 frequency decay 作为 row-level detector 在 `entity_complete_v1` 重跑；price/delivery/SKU/wallet share 不应抢先实现。

