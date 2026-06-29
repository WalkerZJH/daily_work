# 数据泄露防护规则

## 总原则

任何在真实预测时点不可见的信息，都不得进入该 cutoff 样本的特征、编码、候选集、潜在损失估计、模型选择或评估过程。

## 时间边界

每个样本必须显式传入：

```text
entity keys
cutoff_month
H
```

特征窗口：

```text
purchase_time <= cutoff_month
```

标签窗口：

```text
(cutoff_month, cutoff_month + H]
```

## 切分规则

主验证必须采用 rolling-origin temporal split。禁止随机 K-fold 作为主验证。

每个 H 单独做 purged split：

```text
max_train_cutoff + H <= valid_start
```

同一 entity 可以同时出现在 train 和 valid/test，但必须时间方向正确。

## 候选集防护

候选集只能包含 cutoff 及以前已经出现过采购历史的 entity。禁止把未来才首次出现的 entity 加入早期 cutoff。

## 特征防护

所有累计、最近一次、频率、间隔、需求画像和状态历史特征必须带 `_asof_cutoff` 或窗口后缀，并只使用 cutoff 前数据。

禁止：

```text
全历史 last_purchase_time
全历史 purchase_count_total 回填所有 cutoff
全历史 ADI / CV2 / median interval 回填所有 cutoff
预测窗口内 order_phase_code / delivery_state_code
next_purchase_time / days_until_next_purchase 进入 X
purchase_time 直接转 Unix timestamp 进入 X
```

## 编码与预处理防护

高基数字段编码必须 time-aware：

```text
frequency encoding fit on train fold only
target encoding time-aware out-of-fold
CatBoost native categorical handling
group statistical features asof cutoff
```

缺失值填充、标准化、类别映射等 preprocessing 只能 `fit(train)`，再 `transform(valid/test)`。

## 价值估计防护

`value_at_risk_H` 和历史价值/规模特征只能使用 cutoff 前历史估计：

```text
value_at_risk_amount_H = cutoff 前 12 个月平均月采购金额 × H
value_at_risk_quantity_H = cutoff 前 12 个月平均月采购数量 × H
```

禁止使用 cutoff 后 H 窗口真实采购金额或数量作为潜在损失。

允许 cutoff 前可见的历史价值/规模特征进入概率模型，包括历史采购金额/数量窗口汇总、历史月均金额/数量、entity 价值分层和 as-of-cutoff 的 `value_at_risk`。这些字段必须通过消融实验单独比较其对概率质量和业务排序的影响。

## 概率与业务优先级防护

主模型目标只能是：

```text
label_die_H
```

主模型输出：

```text
churn_probability_H
```

业务优先级后处理：

```text
business_priority_score_H = churn_probability_H × value_at_risk_amount_H
```

不得把 `business_priority_score_H` 解释为概率，不得训练 `die_H × value_at_risk_H` 后再命名为流失概率。

## 评估防护

TopK 指标必须先在每个 cutoff 内计算，再做时间聚合。不得把不同 cutoff 的样本混在一起全局排序。

药企输出必须按 `manufacturer_code` 分组，避免跨药企混排。

## 清洗层防护

当前阶段不得修改已冻结的 BS_Agent_DingDan v2 清洗语义。清洗规则可作为全局固定规则使用，但任何随时间变化的统计派生都必须 as-of-cutoff。
