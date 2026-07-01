## 1. 模块定位

M3 是 recurring 主候选的 survival / interval-aware 精查模块。

它只处理：

```text
recurring_business_priority_candidates
```

不处理：

```text
one_shot_attention_candidates
```

M3 不负责全量排序，不重新训练 Stage 1 模型，不输出最终业务排序。它回答：

```text
这个高业务优先级候选是否真的超出了自己的正常采购节奏？
```

M3-v1 不采用 BG/NBD、Pareto/NBD。该路线暂时删除。M3-v1 采用：

```text
survival-lite / interval-aware state machine
```

---

## 2. 输入

M3 输入：

```text
recurring_business_priority_candidates
entity_cutoff_features
demand_shape_label
```

核心字段：

```text
manufacturer_code
hospital_code
drug_group
drug_group_source
cutoff_month
horizon

churn_probability_H
business_priority_score_H
value_at_risk_H

months_since_last_purchase_asof_cutoff
purchase_count_asof_cutoff
active_month_count_asof_cutoff
months_observed_asof_cutoff

adi_asof_cutoff
cv2_quantity_asof_cutoff
median_purchase_interval_days_asof_cutoff
mean_purchase_interval_days_asof_cutoff
std_purchase_interval_days_asof_cutoff
purchase_interval_iqr_asof_cutoff

order_count_last_3m_asof_cutoff
order_count_last_6m_asof_cutoff
order_count_last_12m_asof_cutoff

demand_shape_label
```

---

## 3. ADI / CV² 泄露约束

ADI 和 CV² 可以使用，但必须是：

```text
adi_asof_cutoff
cv2_quantity_asof_cutoff
```

即只使用：

```text
purchase_time <= cutoff_month
```

如果用全历史计算 ADI / CV² 再回填到所有 cutoff，会造成数据泄露。数据泄露风险文档已经明确指出，全历史 ADI、CV²、median purchase interval 回填会让早期样本看到未来采购节奏，正确做法是按 cutoff 动态计算或生成 entity × cutoff 版本。

因此 M3 要求所有 interval/demand-shape 字段必须带 `_asof_cutoff` 语义。

---

## 4. 历史充分性分层

M3 必须先判断历史是否足够。

### 4.1 history_sufficient

条件：

```text
purchase_count_asof_cutoff >= 3
active_month_count_asof_cutoff >= 2
median_purchase_interval_days_asof_cutoff is not null
```

处理：

```text
使用 entity-level interval
```

### 4.2 history_medium

条件：

```text
purchase_count_asof_cutoff >= 3
但 interval variance 高，或 cv2_quantity_asof_cutoff 高
```

处理：

```text
使用 entity interval + group prior interval 混合
```

### 4.3 history_insufficient

条件：

```text
purchase_count_asof_cutoff < 3
或 active_month_count_asof_cutoff < 2
或 interval 不可用
```

处理：

```text
不输出强 survival 状态；
使用 group prior 仅作参考；
survival_confidence = low
```

### 4.4 one_shot

M3 不处理 one-shot：

```text
survival_state = not_applicable_one_shot
```

---

## 5. expected interval 计算

### 5.1 entity-level interval

当历史充分：

```text
expected_interval_days = median_purchase_interval_days_asof_cutoff
```

优先使用 median 而不是 mean，因为采购间隔容易长尾。

### 5.2 group prior interval

当历史不足或 interval 不稳定，使用 group prior。

候选 group：

```text
manufacturer_code × drug_category_code
hospital_level_code × drug_category_code
province_code × drug_category_code
demand_shape_label × drug_category_code
```

group prior 也必须 as-of cutoff 计算。

### 5.3 混合 interval

当 history_medium：

```text
expected_interval_days =
w_entity × median_interval_entity
+
(1 - w_entity) × group_prior_interval
```

其中：

```text
w_entity = min(1, purchase_count_asof_cutoff / 6)
```

### 5.4 单位转换

```text
expected_interval_months = expected_interval_days / 30.4375
```

---

## 6. 核心 survival-lite 指标

```text
overdue_ratio =
months_since_last_purchase_asof_cutoff
/
max(expected_interval_months, epsilon)
```

```text
overdue_gap_months =
months_since_last_purchase_asof_cutoff - expected_interval_months
```

如果有足够历史 interval，可以输出：

```text
interval_percentile =
current_gap 在历史采购间隔分布中的分位数
```

---

## 7. survival_state 规则

初版规则：

```text
if history_insufficient:
    survival_state = insufficient_history

elif demand_shape_label == "lumpy":
    survival_state = low_confidence_lumpy

elif overdue_ratio < 0.8:
    survival_state = normal_interval

elif 0.8 <= overdue_ratio < 1.2:
    survival_state = near_expected_interval

elif 1.2 <= overdue_ratio < 2.0:
    survival_state = slightly_overdue

elif 2.0 <= overdue_ratio < 3.0:
    survival_state = materially_overdue

else:
    survival_state = likely_churn_interval
```

该状态不等于最终流失结论，只表示该 entity 是否超出自身历史采购节奏。

---

## 8. demand-shape 路由

M3 必须保留路由接口。不同需求形态对 survival-lite 的解释不同。

### smooth

```text
survival_method = entity_interval
confidence_multiplier = 1.0
allowed_horizons = H3/H6/H12
alert_policy = normal_probability_alert
```

### erratic

```text
survival_method = entity_interval_with_lower_confidence
confidence_multiplier = 0.75
allowed_horizons = H6/H12 preferred
H3 = cautious
alert_policy = review_required
```

### intermittent

```text
survival_method = group_prior_or_long_horizon
confidence_multiplier = 0.6
allowed_horizons = H12 preferred
H3 = observation_only
alert_policy = observation_or_manual_review
```

### lumpy

```text
survival_method = observation_only
confidence_multiplier = 0.4
allowed_horizons = H12_or_later
alert_policy = no_strong_alert_without_extra_evidence
```

---

## 9. survival_confidence

基础置信度：

```text
base_confidence = min(1, purchase_count_asof_cutoff / 6)
```

形态乘子：

```text
smooth = 1.0
erratic = 0.75
intermittent = 0.6
lumpy = 0.4
```

历史不足惩罚：

```text
if history_insufficient:
    max_confidence = 0.4
```

最终：

```text
survival_confidence =
min(base_confidence × shape_multiplier, max_confidence_if_applicable)
```

---

## 10. 输出表

表名：

```text
survival_refinement_results
```

字段：

```text
candidate_id
manufacturer_code
hospital_code
drug_group
drug_group_source
cutoff_month
horizon

survival_method
expected_interval_months
expected_interval_source
months_since_last_purchase
overdue_ratio
overdue_gap_months
interval_percentile

survival_state
survival_confidence
demand_shape_label
demand_shape_route
demand_shape_adjustment

history_sufficiency_flag
fallback_method
survival_note
human_review_required
```

---

## 11. M3 不做事项

M3 不做：

```text
1. 不训练复杂 survival 模型；
2. 不采用 BG/NBD / Pareto/NBD；
3. 不处理 one-shot；
4. 不改变 churn_probability_H；
5. 不改变 business_priority_score_H；
6. 不生成 detector 证据；
7. 不生成线索卡。
```

---

