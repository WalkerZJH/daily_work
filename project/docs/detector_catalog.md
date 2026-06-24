# Detector 目录

当前 detector 固定使用以下 category：

- `price_warning`
- `delivery_response`
- `terminal_change`
- `sales_fluctuation`
- `common_preprocess`

## 已实现的 terminal_change detector

对外需求 detector：

- `terminal_lost_warning`：终端丢失预警。v1 使用历史采购周期、最后采购时间、当前未采购天数和平均采购数量。
- `new_terminal_warning`：新进终端识别。v1 判断首次采购或 180 天未采购后恢复采购，并检查采购数量阈值。

内部支撑 detector：

- `inactive_terminal`
- `new_terminal`
- `ip_interval`
- `frequency_drop`
- `sku_shrink`
- `substitution_risk`
- `cycle_deviation`

这些 detector 主要用于终端动态和终端变化识别。当前阶段的输出只用于算法验证和风险候选生成，不代表正式预警结论。

## price_warning 类检测器

- `low_price_warning`：低价采购预警。若没有配置 `warning_price`，则不触发，并输出 `MISSING_WARNING_PRICE_CONFIG`。
- `price_spread_warning`：订单价差异常。v1 近期窗口内最高/最低 `comparable_unit_price` 价差规则。默认价差阈值 `spread_ratio_threshold = 1.8`。

价格类 detector 使用 `comparable_unit_price`，不得直接使用原始 `purchase_price` 作为可比价格。

## delivery_response 类检测器

- `delivery_rejection_warning`：拒绝响应预警。v1 关键词规则，基于 `order_status` 中的拒绝、退货、无法配送、缺货、驳回、拒收、撤单等关键词。
- `delivery_delay_warning`：响应不及时预警。v1 使用 `delivery_time - order_time` 的近似口径，并在 warning 中标明该限制；不能解释为“确认订单后 48 小时未发货”。
- `low_delivery_rate_warning`：配送率低预警。v1 口径为 `delivery_qty / purchase_qty`，默认阈值 0.8，后续可按省份配置。

## sales_fluctuation 类检测器

- `purchase_quantity_fluctuation_warning`：采购量异常波动。v1 判断当前采购量超过近 6 月均值 3 倍，或与上月相比骤降。
- `purchase_frequency_fluctuation_warning`：采购频次异常波动。v1 判断近 30 天频次超过近 6 月平均频次 2 倍，或与上月相比骤降。

sales 类 detector 当前使用窗口内日均数量/频次的 v1 规则，输出 `DetectorEvidence`，不输出最终风险概率。

## 输出约束

Detector 输出会统一规范为 `DetectorEvidence`。风险卡片只聚合 evidence family，不对 severity 做加权平均，也不把规则分解释为概率。

health 页面的 `/api/v0/detectors/run` 输出使用统一 `DetectorRunResult`：

- `detector_id`
- `detector_name`
- `name_zh`
- `category`
- `status`
- `hit`
- `severity`
- `confidence`
- `reason_code`
- `metrics`
- `evidence_items`
- `warnings`
- `narrative`

`P(alive)` 相关字段已经预留，但在校准后的主干模型完成前保持 `null` 或实验候选状态。
