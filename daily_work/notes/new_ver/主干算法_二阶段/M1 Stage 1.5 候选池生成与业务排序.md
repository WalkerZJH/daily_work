## 1.1 模块定位

M1 的职责是从 Stage 1 scorer 的全量概率输出中生成：

```text
1. recurring 业务排序高位候选；
2. one-shot 高价值关注表；
3. demand-shape 特殊观察表。
```

其中真正的“高位候选主表”只有第一类：

```text
recurring_business_priority_candidates
```

它的排序依据不是单纯概率，而是：

```text
business_priority_score_H = churn_probability_H × value_at_risk_H
```

M1 不负责 survival，不负责 detector，不负责线索卡自然语言生成。

---

## 1.2 输入

M1 需要读取以下输入。

### Stage 1 probability output

字段：

```text
manufacturer_code
hospital_code
drug_group
drug_group_source
cutoff_month
horizon
churn_probability_H
risk_band_H
demand_shape_label
probability_candidate_version
```

当前版本：

```text
probability_candidate_v1 =
logistic_regression + frequency_decay_v1 + raw
```

### Value history / value_at_risk features

字段：

```text
historical_avg_monthly_amount_asof_cutoff
historical_avg_monthly_quantity_asof_cutoff
purchase_amount_sum_last_3m_asof_cutoff
purchase_amount_sum_last_6m_asof_cutoff
purchase_amount_sum_last_12m_asof_cutoff
```

如果当前金额字段仍是脱敏金额，则 M1 输出只能称为：

```text
relative_value_at_risk
relative_business_priority_score
```

在真实业务环境中可替换为真实金额口径。

### One-shot candidate source

字段：

```text
manufacturer_code
hospital_code
drug_group
drug_group_source
first_purchase_month
first_purchase_amount
first_purchase_quantity
hospital_level_code
ownership_type_code
province_code
city_code
drug_category_code
delivery_state_code
order_failure_flag
```

### Demand-shape review source

字段：

```text
manufacturer_code
hospital_code
drug_group
drug_group_source
cutoff_month
demand_shape_label
horizon
churn_probability_H
label_policy_note
demand_shape_route
```

---

## 1.3 business_priority_score 的窗口问题

你提出的问题是关键：

```text
如果 business_priority_score = 某窗口丢失概率 × 某窗口平均价值，
那评分窗口需要固定。
```

M1 的设计应避免在底层固定唯一窗口。推荐做法是：

```text
分别计算 H3 / H6 / H12 的 business_priority_score；
保留三套分数；
主页或客户配置选择 primary_priority_horizon。
```

即：

```text
business_priority_score_H3 = churn_probability_H3 × value_at_risk_H3
business_priority_score_H6 = churn_probability_H6 × value_at_risk_H6
business_priority_score_H12 = churn_probability_H12 × value_at_risk_H12
```

---

## 1.4 value_at_risk_H 的初版定义

推荐初版定义为窗口价值暴露：

```text
value_at_risk_H =
historical_avg_monthly_purchase_amount_asof_cutoff × H
```

如果存在稳定的历史窗口均值，也可以定义为：

```text
value_at_risk_H =
mean historical purchase amount over rolling H-month windows before cutoff
```

当前建议 v1 采用简单、稳定、可解释版本：

```text
value_at_risk_H =
historical_avg_monthly_amount_asof_cutoff × H
```

原因：

```text
1. 与 H3/H6/H12 自然匹配；
2. 不需要复杂窗口回溯；
3. 低样本时更稳定；
4. 可后续替换为真实 CLV 或客户价值模型。
```

如果金额脱敏，则命名为：

```text
relative_value_at_risk_H
relative_business_priority_score_H
```

不能对外解释为真实货币损失。

---

## 1.5 recurring business priority 主表生成

### Step 1：计算 horizon-level score

对每个 recurring entity × cutoff × H：

```text
business_priority_score_H =
churn_probability_H × value_at_risk_H
```

保留：

```text
H3
H6
H12
```

### Step 2：按 horizon 分别排序

每个 cutoff_month、每个 horizon 下排序。

排序范围使用混合策略：

```text
先全局 top 5%
再按 manufacturer 内部补齐最低数量
```

---

## 1.6 Top 5% + manufacturer 补齐策略

你提出的策略是合理的，M1 固化为默认策略。

### 全局 Top 5%

在同一：

```text
cutoff_month × horizon
```

下，对所有 recurring entity 按：

```text
business_priority_score_H
```

降序排序，取：

```text
global_top_pct = 0.05
```

进入主候选。

### Manufacturer minimum fill

全局 Top 5% 之后，按 `manufacturer_code` 分组检查。

如果某个 manufacturer 在当前 cutoff × horizon 下入选数量少于：

```text
manufacturer_min_candidates = 3
```

则按该 manufacturer 内部的 `business_priority_score_H` 降序补齐到 3 个。

补齐候选需要标注：

```text
selection_reason = manufacturer_min_fill
```

而全局 Top5% 候选标注：

```text
selection_reason = global_top5pct
```

如果某 manufacturer 可用 recurring entity 不足 3 个，则全部保留，并写：

```text
selection_note = available_entities_less_than_minimum
```

---

## 1.7 多 horizon 候选折叠

同一个 entity 可能在 H3、H6、H12 多个 horizon 中被选中。

M1 应保留 horizon-level 明细表，同时生成 entity-level 主表。

### horizon-level 明细表

```text
recurring_business_priority_candidates_by_horizon
```

字段：

```text
manufacturer_code
hospital_code
drug_group
drug_group_source
cutoff_month
horizon
churn_probability_H
value_at_risk_H
business_priority_score_H
rank_global
rank_within_manufacturer
selection_reason
```

### entity-level 主表

```text
recurring_business_priority_candidates
```

按 entity × cutoff 折叠。

字段：

```text
manufacturer_code
hospital_code
drug_group
drug_group_source
cutoff_month
selected_horizons
primary_horizon
primary_business_priority_score
primary_churn_probability
primary_value_at_risk
candidate_selection_reasons
rank_global_primary_horizon
rank_within_manufacturer_primary_horizon
```

### primary_horizon 选择

M1 不应强行只保留一个窗口，但 entity-level 表需要一个主视角。推荐：

```text
默认 primary_horizon = H6
```

如果某 entity 未在 H6 被选中，但在 H3 或 H12 被选中，则：

```text
primary_horizon = 该 entity business_priority_score_H 最高的 horizon
```

同时保留：

```text
selected_horizons = ["H3", "H12"]
```

这样后续 survival / detector 知道它在哪些窗口上被关注。

---

## 1.8 one-shot high value 旁路表

one-shot 不进入主业务排序表。

M1 只生成或接收 one-shot attention 表，不详细定义模型。具体 one-shot 风险估计放到 M2。

M1 对 one-shot 的要求是：

```text
1. 单独输出 one_shot_attention_candidates；
2. 不与 recurring_business_priority_candidates 合并；
3. 不输出 churn_probability_H；
4. 不使用 business_priority_score_H；
5. 只输出 one_shot_attention_score 或 one_shot_value_rank。
```

字段：

```text
manufacturer_code
hospital_code
drug_group
drug_group_source
first_purchase_month
first_purchase_amount
one_shot_value_score
one_shot_similarity_risk_score
one_shot_attention_score
attention_rank
attention_reason
probability_available
probability_interpretation
```

固定语义：

```text
probability_available = false
probability_interpretation = not_recurring_churn_probability
```

你提出的 KMeans / 相似医院方案属于 M2 详细设计。M1 只保留接口：

```text
one_shot_similarity_risk_score
similarity_method
similar_reference_group
```

---

## 1.9 demand-shape observation 旁路表

特殊 demand-shape 不进入主业务排序表。

M1 只输出观察表：

```text
demand_shape_observation_candidates
```

适用对象：

```text
1. intermittent H3 高风险但不适合强预警；
2. lumpy 高风险但置信度不足；
3. demand-shape guardrail 认为需要观察而非业务高位候选的对象。
```

字段：

```text
manufacturer_code
hospital_code
drug_group
drug_group_source
cutoff_month
horizon
churn_probability_H
demand_shape_label
demand_shape_route
observation_reason
recommended_observation_window
probability_interpretation
```

示例：

```text
observation_reason = intermittent_H3_observation_only
recommended_observation_window = H12
```

它不参与：

```text
business_priority_score 排序
survival 主精查队列
detector 主精查队列
```

除非后续模块显式配置要对 observation 表做轻量 detector。

---

## 1.10 重复对象处理

逻辑表之间不取并集，但首页展示可能需要去重。

去重优先级：

```text
1. recurring_business_priority_candidates
2. demand_shape_observation_candidates
3. one_shot_attention_candidates
```

如果某对象同时出现在多个表：

```text
只保留最高优先级展示位置。
```

不需要把所有原因都塞回主排序，因为后续 detector / survival 会补充完整风险信息。

但为了审计，可以保留一个隐藏字段：

```text
suppressed_display_sources
```

例如：

```text
suppressed_display_sources = ["demand_shape_observation"]
```

这个字段不参与业务展示，只用于 debug。

---

## 1.11 M1 输出

M1 最终输出三类表。

### 1. recurring_business_priority_candidates_by_horizon

用于审计和指标分析。

### 2. recurring_business_priority_candidates

主表。后续 M3 survival / M4 detector 默认读取这个表。

### 3. one_shot_attention_candidates

one-shot 旁路首页关注表。

### 4. demand_shape_observation_candidates

特殊需求形态观察表。

虽然是四张输出，但可以理解为：

```text
1 张主表 + 2 张旁路展示表 + 1 张审计明细表
```

---

## 1.12 M1 不做什么

M1 不做：

```text
1. 不训练新模型；
2. 不修改 churn_probability；
3. 不计算 survival_state；
4. 不运行 detector；
5. 不把 one-shot 当 recurring 概率；
6. 不把 demand-shape observation 并入主候选表；
7. 不生成线索卡；
8. 不调用 LLM；
9. 不自动派单。
```

---

# M0 + M1 当前决策摘要

## 已确定

```text
1. 主预测粒度是 manufacturer × hospital × drug_code。
2. drug_group 是抽象字段，当前 source = drug_code。
3. 主高位候选只来自 business_priority 排序。
4. business_priority_score_H = churn_probability_H × value_at_risk_H。
5. H3/H6/H12 分别计算，不在底层强行压成一个分数。
6. 默认主页 primary horizon 可先用 H6，但保留配置。
7. 主候选筛选采用 global top 5% + manufacturer min-fill。
8. one-shot high value 单独成表，不并入主候选。
9. demand-shape observation 单独成表，不并入主候选。
10. 表间展示去重优先级为 business > demand-shape > one-shot。
```

## 待后续模块解决

```text
1. M2：one-shot attention_score / similarity_risk_score 如何具体计算；
2. M3：survival-lite 如何设计，历史不足如何降级；
3. M4：四大类 detector 的具体算法方案；
4. M5：survival + detector evidence 如何融合成状态；
5. M6：detector cache 如何设计；
6. M7：structured evidence bundle 如何供 LLM 使用；
7. M8：如何评估这些模块是否有效。
```