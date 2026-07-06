# Abandoned or Deferred Designs

## 已放弃或不采用

1. BG/NBD / Pareto-NBD：M3-v1 删除或延后，不进入当前主线。
2. formal survival / Cox / AFT / discrete-time survival：当前不实现，保留为未来研究方向。
3. one-shot 复用 recurring churn scorer：新链路 one-shot 诊断效果差，不能作为 repeat probability。
4. supplier-switch / competitor-substitution 正式标签：当前 choice-set 只是 partial platform context，不能解释为完整市场替代或竞品替代。
5. detector severity/confidence 融合成新概率：明确禁止。
6. auto dispatch：明确禁止，`auto_dispatch_allowed=false`。
7. customer-facing probability service：当前阶段不建议。

## 当前降级为 interface-only

1. `low_price_purchase_warning`：缺可靠可比价、规格/单位映射、价格口径确认。
2. `order_price_spread_warning`：同上。
3. `purchase_amount_trend_warning`：金额字段为相对/脱敏语义，不能直接解释真实金额趋势。
4. M6 cache/timeline：仅保留接口字段，不实现读写和趋势。
5. LLM line card：仅保留 structured material，未调用 LLM。

## 当前 intentionally_deferred

1. `rejection_response_warning`
2. `delayed_response_warning`
3. `low_delivery_rate_warning`
4. `purchase_quantity_trend_warning`
5. `sku_narrowing_warning`
6. `wallet_share_decline_warning`
7. L2/L3/FDR 融合升级

## 降级原因

- price：价格被脱敏或缺可比价口径。
- delivery：delivery_time / arrival_time 缺失或回填口径不稳定。
- SKU/wallet share：缺产品线/portfolio mapping，且 choice-set 不是完整市场。
- one-shot：业务语义是 first-purchase repeat propensity，不是 recurring churn。
- M6/LLM：上游 M1-M5 当前链路尚未稳定，过早实现会增加复杂度和误用风险。

## 结论

这些不是失败项，而是当前 v1 的边界。对领导汇报时应说“已明确边界和延后项”，不要说“全部未做”或“全部完成”。

