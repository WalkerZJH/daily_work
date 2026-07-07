# Detector Business Readiness Summary

detector 没有全部完成。当前可用于业务展示的是规则型证据，不是完整根因归因，也不是概率。

- enabled_rule_v1: ['terminal_loss_warning', 'purchase_interval_overdue_warning', 'purchase_frequency_fluctuation_warning', 'new_terminal_detection']
- weak_enabled_review_required: ['purchase_quantity_fluctuation_warning', 'low_delivery_rate_warning']
- interface_only / internal_only: ['low_price_purchase_warning', 'order_price_spread_warning', 'purchase_amount_trend_warning']
- deferred: ['rejection_response_warning', 'delayed_response_warning', 'sku_narrowing_warning', 'wallet_share_decline_warning']

配送时间类 detector 暂不做：`delivery_time` / `arrival_time` 缺失率和回填稳定性不足，不能支持配送时效分析，也不能形成配送商责任结论。

price / sku / wallet share 暂不强做：价格缺少可比价口径，SKU/portfolio 缺少稳定产品线映射，choice-set 不是完整市场上下文。

前端展示 disabled detector 时，应显示“暂未启用 / 数据质量不足 / 需补充业务映射”，不得显示确定性归因。
