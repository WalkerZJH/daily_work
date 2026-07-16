# Demand-shape Detector 阈值建议

当前 v1 从同一 cleaned Detector 订单事实按观察日计算 demand shape，不依赖月度预测特征表。

| demand shape | 阈值策略 | 最低样本策略 | 当前状态 |
|---|---|---|---|
| smooth | 基础阈值 | 基础样本 | provisional_v1 |
| erratic | 上升更严格、下降阈值下调 | 提高 | provisional_v1 |
| intermittent | 明显更严格 | 明显提高 | provisional_v1 |
| lumpy | 最严格 | 最高 | provisional_v1 |

## 当前实体分布

| demand_shape | entity_count |
| --- | --- |
| intermittent | 37812 |
| lumpy | 9060 |
| smooth | 930 |
| erratic | 180 |

这些 modifier 已版本化进入企业 profile，但业务验收前不得宣称为优化阈值。
