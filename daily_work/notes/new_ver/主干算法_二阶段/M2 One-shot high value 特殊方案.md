## 1. 模块定位

M2 负责处理 **one-shot high value attention** 对象，即只有一次采购记录、但采购金额或业务价值较高的医院-药品关系。

该模块不属于 recurring churn probability 主模型，不输出 `churn_probability_H`。它解决的是另一个问题：

```text
首次采购后，该医院-药品关系是否有机会转化为持续采购关系？
```

因此 M2 的核心预测目标为：

```text
repeat_probability_H = P(second_purchase_within_H | first_purchase_context)
```

对应的非复购风险为：

```text
one_shot_non_repeat_risk_H = 1 - repeat_probability_H
```

注意：

```text
one_shot_non_repeat_risk_H 不是 recurring churn_probability_H。
```

M2 输出的分数只用于 one-shot 专项关注列表，不进入 recurring 主概率模型，也不参与 recurring business priority 主表。

---

## 2. 与主线关系

M2 接收 M1 输出的：

```text
one_shot_attention_candidates
```

并对其中的 one-shot 高价值对象补充：

```text
repeat_probability_H
one_shot_non_repeat_risk_H
one_shot_attention_score
explanation_factors
similarity_group_explanation
manual_review_required
```

M2 输出后进入后续：

```text
structured evidence bundle
```

但默认不进入：

```text
recurring_business_priority_candidates
survival-lite recurring 精查
recurring churn probability model
```

---

## 3. 训练样本定义

M2 的训练样本不应只来自 recurring entity，而应来自所有历史上出现过首次采购的 entity，只要其未来标签窗口闭合。

样本索引事件：

```text
first_purchase_event
```

样本粒度：

```text
manufacturer_code × hospital_code × drug_group × first_purchase_month
```

其中：

```text
drug_group_source = drug_code
```

当前 `drug_group` 的 primary source 是 `drug_code`，因此实际粒度为 `manufacturer_code × hospital_code × drug_code`，不是药品大类。配置文件中 entity grain 为 `manufacturer_code / hospital_code / drug_group`，并明确 `primary_drug_group_source: drug_code`。

标签定义：

```text
label_repeat_H = 1
if second_purchase_time in (first_purchase_time, first_purchase_time + H]

label_repeat_H = 0
if H window 内没有第二次采购
```

支持窗口：

```text
H3
H6
H12
```

初版推荐主展示窗口：

```text
H6 或 H12
```

H3 对 one-shot 转化判断可能过短，仅作为补充观察。

---

## 4. 数据泄露约束

M2 所有特征必须来自首次采购当时或首次采购前可见的信息。

允许：

```text
first_purchase_time 及以前的医院、药品、地区、历史群体统计、首次采购订单信息
```

禁止：

```text
第二次采购是否发生
首次采购后的订单数量
未来是否成为 recurring
未来 value
未来 label
全量 target encoding
用全历史统计回填到早期 first_purchase_time
```

群体先验必须是 as-of first_purchase_time 的历史统计。例如：

```text
province × hospital_level 的历史复购率
drug_category × manufacturer 的历史复购率
```

必须只使用 `first_purchase_time` 之前已发生的数据。

---

## 5. 特征分组

### 5.1 医院上下文特征

```text
hospital_level_code
ownership_type_code
province_code
city_code
county_code
hospital_historical_activity_prior
hospital_level_repeat_rate_prior
province_repeat_rate_prior
province_hospital_level_repeat_rate_prior
```

解释含义：

```text
该地区、该医院等级、该机构类型历史上是否更容易形成复购关系。
```

### 5.2 药品上下文特征

```text
drug_group
drug_category_code
manufacturer_code
drug_group_repeat_rate_prior
drug_category_repeat_rate_prior
manufacturer_repeat_rate_prior
manufacturer_drug_category_repeat_rate_prior
province_drug_category_repeat_rate_prior
```

解释含义：

```text
该药品、药品类别、生产企业历史上是否更容易带来复购。
```

### 5.3 首次采购强度特征

```text
first_purchase_quantity
first_purchase_amount
first_purchase_amount_percentile_within_drug
first_purchase_quantity_percentile_within_drug
first_purchase_amount_percentile_within_hospital_level
first_purchase_amount_percentile_within_province
```

解释含义：

```text
首次采购是零星试采，还是具有较强采购强度。
```

如果金额字段仍是脱敏金额，则所有金额相关字段只能解释为：

```text
relative purchase amount
relative value score
```

不能解释为真实货币损失。

### 5.4 首次采购履约与状态特征

可用：

```text
delivery_rate
arrival_rate
overall_arrival_rate
order_phase_code
delivery_state_code
order_terminal_flag
order_failure_flag
return_quantity
```

暂不使用：

```text
delivery_time
arrival_time
```

原因是配送时间和到货时间缺失率较高，时间型履约判断不稳定。

---

## 6. 模型方案

M2 直接采用 B 方案：**first-purchase repeat propensity model**。

### 6.1 主模型

推荐初版：

```text
regularized logistic regression
```

目标：

```text
repeat_probability_H
```

理由：

```text
1. 输出概率语义清晰；
2. 可解释；
3. 与当前主干 Logistic 风格一致；
4. 对样本规模要求较低；
5. 可以输出方向性解释；
6. 便于做 group prior 和冷启动 fallback。
```

不建议把 KMeans 作为主模型。KMeans 更适合作为相似群体解释和 fallback，而不是主概率估计器。

---

## 7. 群体先验与平滑

对低样本 group，需要使用平滑后的复购率。

通用形式：

```text
smoothed_repeat_rate =
(group_positive + global_repeat_rate × prior_strength)
/
(group_count + prior_strength)
```

推荐 group：

```text
province × hospital_level
hospital_level × drug_category
province × drug_category
manufacturer × drug_category
manufacturer × province
similarity_cluster
```

这些先验既可作为模型特征，也可作为解释依据。

---

## 8. 相似群体 / KMeans 解释方案

KMeans 不作为主模型，但可以作为相似群体解释模块。

输入特征：

```text
hospital_level_code
province_code
city_code
ownership_type_code
drug_category_code
manufacturer_code
first_purchase_amount_percentile
first_purchase_quantity_percentile
```

输出：

```text
similarity_group_id
similar_group_repeat_rate_H
similar_group_sample_count
similarity_explanation
```

解释示例：

```text
该 one-shot 对象与历史上“同省份、同医院等级、同药品类别、首次采购强度相近”的样本较接近；该相似群体在 H6 内的历史复购率为 xx%。
```

禁止解释为：

```text
KMeans 判断它会流失。
```

---

## 9. one-shot 推荐策略

当前需求侧尚未确认 one-shot 应优先推荐“更容易复购”还是“更不容易复购”的对象。因此 M2 初版同时输出三套分数。

### 9.1 保价值 / 防不复购策略

```text
one_shot_retention_risk_score_H =
one_shot_non_repeat_risk_H × one_shot_value_score
```

适用假设：

```text
优先挽回高价值但可能不复购的新终端。
```

风险：

```text
非复购风险极高的对象，可能即使投入也难以改变结果。
```

### 9.2 转化机会策略

```text
one_shot_conversion_opportunity_score_H =
repeat_probability_H × one_shot_value_score
```

适用假设：

```text
优先跟进最可能转化为稳定采购关系的高价值新终端。
```

风险：

```text
这些对象可能即使不干预也会复购。
```

### 9.3 平衡关注策略

```text
one_shot_balanced_attention_score_H =
repeat_probability_H × one_shot_non_repeat_risk_H × one_shot_value_score
```

适用假设：

```text
过高复购概率：可能不需要干预；
过低复购概率：可能干预也无效；
中间不确定区间：最可能存在可改变空间。
```

注意：

```text
这不是 uplift 模型，只是机会分启发式。
```

### 9.4 默认策略

在需求侧未确认前，默认输出三套分数，并配置：

```text
selected_attention_policy = configurable
```

内部可先用：

```text
balanced_attention_score
```

作为默认展示分，但必须允许切换。

---

## 10. 输出表

表名：

```text
one_shot_attention_candidates
```

字段：

```text
manufacturer_code
hospital_code
drug_group
drug_group_source
first_purchase_month
horizon

repeat_probability_H
one_shot_non_repeat_risk_H
repeat_probability_interpretation

one_shot_value_score
one_shot_retention_risk_score_H
one_shot_conversion_opportunity_score_H
one_shot_balanced_attention_score_H
selected_attention_score
selected_attention_policy

top_explanation_factors
group_prior_explanation
similarity_group_id
similarity_group_explanation
similar_group_repeat_rate_H
similar_group_sample_count

model_confidence
manual_review_required
probability_available
probability_interpretation
```

固定字段：

```text
probability_available = true for repeat_probability_H
probability_interpretation = first_purchase_repeat_probability_not_recurring_churn_probability
```

同时明确：

```text
repeat_probability_H 可以解释为首次采购后复购概率；
one_shot_non_repeat_risk_H 不能解释为 recurring churn_probability_H。
```

---

## 11. 可解释性输出

M2 必须同步输出解释，不能只输出分数。

解释最小结构：

```text
explanation_type
feature_or_group
direction
contribution_level
message
```

解释类型包括：

```text
hospital_context
regional_prior
drug_context
first_purchase_strength
fulfillment_status
similarity_group
```

示例：

```text
regional_prior:
该省份同等级医院历史 H6 复购率较高，因此 repeat_probability 上调。

first_purchase_strength:
首次采购金额处于同药品历史分布较高分位，说明首次采购强度较高。

drug_context:
该药品类别历史复购率较低，因此 repeat_probability 下调。
```

初版可以使用静态解释，即基于 group prior、分位数和模型方向生成，不要求 SHAP。

---
