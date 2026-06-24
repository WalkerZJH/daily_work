# Detector 目录

当前 detector 固定使用以下 category：

- `price_warning`
- `delivery_response`
- `terminal_change`
- `sales_fluctuation`
- `common_preprocess`

## 已实现的 terminal_change detector

- `inactive_terminal`
- `new_terminal`
- `ip_interval`
- `frequency_drop`
- `sku_shrink`
- `substitution_risk`
- `cycle_deviation`

这些 detector 主要用于终端动态和终端变化识别。当前阶段的输出只用于算法验证和风险候选生成，不代表正式预警结论。

## price_warning 类检测器

- `low_price`：v1 阈值规则。若没有配置 `warning_price`，则不触发，并输出 `LOW_PRICE_THRESHOLD_NOT_CONFIGURED`。
- `price_spread`：v1 近期窗口内最高/最低 `comparable_unit_price` 价差规则。默认价差阈值 `spread_ratio_threshold = 1.8`。

价格类 detector 使用 `comparable_unit_price`，不得直接使用原始 `purchase_price` 作为可比价格。

## delivery_response 类检测器

- `delivery_refusal`：v1 轻量关键词规则，基于 `order_status` 中的拒绝、退货、无法配送、缺货、驳回等关键词。
- `delivery_delay`：占位。当前只有 `delivery_time - order_time` 的近似口径，不能解释为“确认订单后 48 小时未发货”。
- `low_delivery_rate`：目录中预留；后续可启用轻量订单级配送率规则。

## 输出约束

Detector 输出会统一规范为 `DetectorEvidence`。风险卡片只聚合 evidence family，不对 severity 做加权平均，也不把规则分解释为概率。

`P(alive)` 相关字段已经预留，但在校准后的主干模型完成前保持 `null` 或实验候选状态。
