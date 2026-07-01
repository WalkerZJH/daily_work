## 1. 模块定位

M7 是 structured evidence bundle 模块。

它不是线索卡，不生成自然语言文案，也不调用 LLM。它只负责把 M1–M5 的结构化输出整理成统一的线索卡原材料。

未来 LLM / MCP / 前端线索卡生成模块只消费 M7 输出，不参与判断。

---

## 2. 输入

M7 输入包括：

```text
M1 recurring_business_priority_candidates
M2 one_shot_attention_candidates_enriched
M3 survival_refinement_results
M4 detector_evidence_results
M5 candidate_status_decision
M6 evidence timeline interface fields
demand-shape guardrails
```

其中 M6 当前仅为预留接口，不提供实际 timeline。

---

## 3. 输出

输出表：

```text
structured_evidence_bundle
```

字段：

```text
bundle_id
candidate_id
candidate_type

manufacturer_code
hospital_code
drug_group
drug_group_source
cutoff_month
horizon

candidate_source
final_candidate_status
review_priority
human_review_required
auto_dispatch_allowed

churn_probability_H
churn_probability_interpretation
repeat_probability_H
repeat_probability_interpretation

value_at_risk_H
business_priority_score_H
business_priority_interpretation

survival_state
survival_confidence
survival_summary

demand_shape_label
demand_shape_route
label_confidence_weight
guardrail_summary

detector_evidence_list
detector_hit_count
strong_detector_hit_count
evidence_strength

evidence_timeline_available
evidence_timeline_reference
evidence_persistence_summary

allowed_claims
forbidden_claims
recommended_action_candidates
model_limitations_note
data_quality_note
```

---

## 4. candidate_type

枚举：

```text
recurring_business_priority
one_shot_attention
demand_shape_observation
```

### recurring_business_priority

来自主表：

```text
recurring_business_priority_candidates
```

有：

```text
churn_probability_H
business_priority_score_H
survival_result
detector_evidence
```

### one_shot_attention

来自：

```text
one_shot_attention_candidates
```

有：

```text
repeat_probability_H
one_shot_attention_score
```

没有：

```text
recurring churn_probability_H
recurring survival_state
```

### demand_shape_observation

来自：

```text
demand_shape_observation_candidates
```

用于观察，不强预警。

---

## 5. allowed_claims

M7 必须明确允许后续 LLM 使用哪些事实。

示例：

```text
该对象进入业务优先级候选池；
该对象的 H6 流失概率为 xx；
该对象的业务优先级较高；
该对象当前 survival_state 为 materially_overdue；
该对象近期采购频次相对历史水平下降；
该对象属于 intermittent，H3 结果需谨慎；
该 one-shot 对象的 H6 复购概率为 xx；
该 one-shot 分数不是 recurring 流失概率。
```

---

## 6. forbidden_claims

M7 必须明确禁止后续 LLM 生成无证据因果断言。

禁止：

```text
医院已经确定流失；
医院一定不会再采购；
医院主动弃用；
竞品替代；
政策落标；
配送商责任；
价格异常导致流失；
低风险对象一定安全；
高风险对象一定流失；
该 one-shot 的 churn_probability 是 xx。
```

除非后续对应 detector 明确提供证据，否则不得生成相关结论。

---

## 7. recommended_action_candidates

M7 可以输出建议动作候选，但不生成最终自然语言线索卡。

示例：

### recurring high priority

```text
建议人工核查近期采购频次下降原因；
建议结合医院实际采购计划判断是否正常延迟；
建议业务人员复核是否存在需求变化。
```

### intermittent / lumpy

```text
建议进入观察清单；
建议优先查看更长窗口；
不建议仅因 H3 未采购直接预警。
```

### one-shot

```text
建议业务人员判断是否需要促进第二次采购；
建议复核首次采购是否为试采；
建议结合医院等级、地区和药品类别判断转化机会。
```

---

## 8. auto_dispatch_allowed

当前固定：

```text
auto_dispatch_allowed = false
```

理由：

```text
1. 当前仍需人工复核；
2. detector 证据不完整；
3. demand-shape guardrails 仍需业务确认；
4. one-shot 不具备 recurring churn 概率语义；
5. 尚未接入真实工单反馈。
```

---

## 9. M7 不做事项

M7 不做：

```text
1. 不训练模型；
2. 不重新排序；
3. 不运行 detector；
4. 不计算 survival；
5. 不调用 LLM；
6. 不生成最终线索卡；
7. 不自动派单。
