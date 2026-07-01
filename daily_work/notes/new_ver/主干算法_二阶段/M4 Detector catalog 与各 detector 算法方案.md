
# M4_detector_catalog_and_rule_design.md

## 1. 模块定位

M4 是 detector evidence 模块。

它只对候选对象运行，不全量运行。它的职责是：

```text
补充证据；
解释风险原因；
支持人工复核；
为 structured evidence bundle 提供结构化 evidence。
```

M4 不负责：

```text
训练主模型；
更新 churn_probability；
计算 business_priority；
自动派单；
生成自然语言线索卡。
```

---

## 2. 四大 detector family

需求文档中的 detector 应按四大业务类型组织：

```text
1. price_warning
2. delivery_response
3. terminal_dynamic
4. sales_fluctuation
```

基本需求文档明确列出价格异常监控、配送响应跟踪、终端动态识别、销量波动分析。 需求原型中也将规则筛选类型列为“价格预警 / 配送响应 / 丢失新进 / 销量波动”。

---

## 3. 统一 detector 输出接口

所有 detector 必须输出统一结构：

```text
candidate_id
manufacturer_code
hospital_code
drug_group
drug_group_source
cutoff_month
horizon

detector_family
detector_name
detector_version

hit_flag
severity
confidence

evidence_window_start
evidence_window_end
evidence_fields
evidence_values

reason_code
business_interpretation
human_review_required
data_quality_status
data_quality_note
```

字段语义：

```text
hit_flag：是否命中 detector
severity：异常程度，不是概率
confidence：证据可信度，不是概率
business_interpretation：业务解释，不得做无依据因果断言
```

---

## 4. price_warning detector family

### 4.1 low_price_purchase_warning

作用：

```text
识别低于客户预警价或同品规异常低价订单。
```

需求依据：价格异常监控中包括低价预警和跨省价差阈值。

v1 状态：

```text
interface_only
```

原因：

```text
当前 purchase_price 可能被独立脱敏，不适合直接判断真实低价。
```

可启用条件：

```text
price_reliable_flag = true
customer_warning_price available
comparable_unit_price available
```

规则：

```text
if comparable_purchase_price < customer_warning_price:
    hit_flag = true
```

输出：

```text
price_deviation_ratio
customer_warning_price
comparable_purchase_price
```

如果价格不可用：

```text
hit_flag = false
data_quality_status = not_evaluable
data_quality_note = purchase_price_independently_desensitized_or_missing
```

---

### 4.2 order_price_spread_warning

作用：

```text
识别同品规跨医院/跨地区价差异常。
```

规则：

```text
same_drug_price_spread_ratio =
max(comparable_price) / min(comparable_price)
```

需求示例中曾使用 1.8 倍价差阈值。价格规则中要求同药品编码、同规格、同剂型、同采购单位统一折算至最小制剂单位后比较最高价和最低价。

v1 状态：

```text
interface_only
```

---

## 5. delivery_response detector family

### 当前决策

配送类 detector 暂不实现，只保留接口。

原因：

```text
delivery_time / arrival_time 缺失率超过 50%，时间型响应分析不可靠。
```

配送相关规则在需求中包括拒绝响应、响应不及时、配送率低。 但当前数据条件不足，不能稳定实现响应不及时类 detector。

---

### 5.1 rejection_response_warning

未来作用：

```text
识别拒绝配送、无法配送、缺货、拒绝响应等订单状态。
```

未来输入：

```text
delivery_state_code
order_failure_flag
order_phase_code
order_status_raw
```

v1 状态：

```text
interface_only
```

---

### 5.2 delayed_response_warning

未来作用：

```text
识别确认订单后超过 N 小时 / N 天仍未发货。
```

未来输入：

```text
purchase_time
delivery_time
order_phase_code
```

v1 状态：

```text
not_implemented_due_to_missing_delivery_time
```

---

### 5.3 low_delivery_rate_warning

未来作用：

```text
识别配送数量 / 采购数量低于阈值。
```

需求中配送率低于 80% 是典型预警口径。

可选弱实现：

```text
delivery_rate = delivery_quantity / purchase_quantity
hit if delivery_rate < 0.8
```

但默认先不启用。若启用，必须：

```text
confidence = low_to_medium
human_review_required = true
data_quality_note = quantity_based_without_delivery_time_validation
```

---

## 6. terminal_dynamic detector family

### 6.1 terminal_loss_warning

作用：

```text
识别长期未采购风险。
```

该 detector 消费：

```text
Stage 1 churn_probability_H
M3 survival_state
demand_shape_route
```

规则：

```text
hit_flag = true
if survival_state in ["materially_overdue", "likely_churn_interval"]
and demand_shape_route not in ["observation_only"]
```

severity 可由以下字段组合：

```text
overdue_ratio
churn_probability_H
business_priority_score_H
```

但不得生成新的概率。

业务解释：

```text
该医院-药品关系距离上次采购已超过其历史采购间隔，存在终端流失风险，建议人工核查。
```

禁止解释：

```text
医院已经确定不采购。
```

---

### 6.2 new_terminal_detection

作用：

```text
识别首次采购或长期未采购后重新采购的终端。
```

规则：

```text
first_seen_entity = true
or no_purchase_in_prior_180_days = true
```

输出：

```text
new_terminal_type:
- first_seen
- reactivated_after_180d
```

M2 one-shot repeat propensity 模块负责进一步判断 one-shot 是否值得关注。M4 这里只输出“新进事实”。

---

## 7. sales_fluctuation detector family

### 7.1 purchase_quantity_fluctuation_warning

作用：

```text
识别采购量异常上升或下降。
```

需求中销量波动分析关注订单量或采购频次显著偏离历史均值。 具体规则示例包括采购量超过近 6 个月均值 3 倍，或较上月骤降。

输入：

```text
purchase_quantity_sum_last_1m
purchase_quantity_sum_last_3m
purchase_quantity_sum_last_6m
historical_avg_monthly_quantity_asof_cutoff
historical_median_monthly_quantity_asof_cutoff
```

v1 规则：

```text
quantity_spike:
recent_quantity > 3 × historical_avg_quantity

quantity_drop:
recent_quantity < drop_threshold × historical_avg_quantity
```

稳健版本：

```text
robust_z =
(recent_quantity - historical_median_quantity) / MAD
```

输出：

```text
quantity_spike_flag
quantity_drop_flag
severity
confidence
```

解释：

```text
近期采购量相对历史水平明显上升 / 下降。
```

---

### 7.2 purchase_frequency_fluctuation_warning

作用：

```text
识别采购频次异常上升或下降。
```

输入：

```text
order_count_last_1m
order_count_last_3m
order_count_last_6m
order_count_last_12m
frequency_decay_3m_vs_12m
frequency_decay_6m_vs_12m
```

需求中采购频次异常波动包括近 30 天采购次数超过近 6 个月平均频次 2 倍，或较上月骤降。

v1 规则：

```text
frequency_spike:
recent_frequency > 2 × historical_frequency

frequency_drop:
frequency_decay_3m_vs_12m < threshold
```

推荐初始阈值：

```text
frequency_decay_3m_vs_12m < 0.5
frequency_decay_6m_vs_12m < 0.6
```

这些阈值后续应通过回测校准。

输出：

```text
frequency_spike_flag
frequency_drop_flag
frequency_decay_value
severity
confidence
```

解释：

```text
近期采购频次相对自身历史频次明显下降 / 上升。
```

---

## 8. v1 实现优先级

### P0：必须实现或优先实现

```text
terminal_loss_warning
purchase_frequency_fluctuation_warning
```

原因：

```text
与当前 probability_candidate_v1 / frequency_decay_v1 / survival-lite 最直接衔接。
```

### P1：可实现

```text
purchase_quantity_fluctuation_warning
new_terminal_detection
```

原因：

```text
规则简单，可解释，适合补充证据。
```

### P2：接口保留

```text
low_price_purchase_warning
order_price_spread_warning
```

原因：

```text
依赖可靠价格口径。
```

### P3：接口保留，暂不实现

```text
rejection_response_warning
delayed_response_warning
low_delivery_rate_warning
```

原因：

```text
配送时间缺失率高，当前分析不可靠。
```

---

## 9. detector 不做事项

M4 不做：

```text
1. 不训练复杂机器学习；
2. 不全量运行；
3. 不改变 churn_probability_H；
4. 不改变 business_priority_score_H；
5. 不把 severity 当概率；
6. 不输出无证据因果解释；
7. 不调用 LLM；
8. 不自动派单。
```

---

