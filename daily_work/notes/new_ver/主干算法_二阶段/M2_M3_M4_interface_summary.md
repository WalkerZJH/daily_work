## 1. 总体数据流

```text
M1 recurring_business_priority_candidates
        │
        ▼
M3 survival-lite / interval-aware refinement
        │
        ▼
M4 terminal_dynamic + sales_fluctuation detectors
        │
        ▼
structured evidence bundle later

M1 one_shot_attention_candidates
        │
        ▼
M2 repeat propensity + one-shot explanation
        │
        ▼
M4 new_terminal_detection
        │
        ▼
structured evidence bundle later

M1 demand_shape_observation_candidates
        │
        ▼
M3 route-only / observation-only
        │
        ▼
M4 optional detector evidence if configured
```

---

## 2. M2 输出到后续模块

M2 输出：

```text
one_shot_attention_candidates_enriched
```

关键字段：

```text
repeat_probability_H
one_shot_non_repeat_risk_H
one_shot_value_score
selected_attention_score
selected_attention_policy
explanation_factors
similarity_group_explanation
model_confidence
manual_review_required
```

进入后续：

```text
structured evidence bundle
new_terminal_detection
```

不进入：

```text
recurring survival-lite
recurring churn_probability model
recurring business_priority table
```

---

## 3. M3 输出到 M4

M3 输出：

```text
survival_refinement_results
```

关键字段：

```text
survival_state
survival_confidence
overdue_ratio
overdue_gap_months
expected_interval_months
demand_shape_route
history_sufficiency_flag
fallback_method
```

M4 的 `terminal_loss_warning` 使用：

```text
survival_state
overdue_ratio
demand_shape_route
```

---

## 4. M4 输出到后续 evidence bundle

M4 输出：

```text
detector_evidence_results
```

关键字段：

```text
detector_family
detector_name
hit_flag
severity
confidence
reason_code
business_interpretation
evidence_fields
evidence_values
human_review_required
data_quality_status
```

进入：

```text
structured evidence bundle
```

不进入：

```text
probability retraining
business_priority recalculation
automatic dispatch
```

---

## 5. 统一语义约束

### 可解释为概率

```text
churn_probability_H
repeat_probability_H
```

但二者含义不同：

```text
churn_probability_H：recurring entity 的未来 H 窗口流失概率
repeat_probability_H：one-shot 首次采购后 H 窗口复购概率
```

### 不可解释为概率

```text
business_priority_score_H
one_shot_attention_score
one_shot_value_score
survival_confidence
detector_severity
detector_confidence
```

---

## 6. 近期实现顺序建议

```text
1. M1 candidate table prototype
2. M2 one-shot repeat propensity prototype
3. M3 survival-lite prototype
4. M4 terminal_loss_warning + purchase_frequency_fluctuation_warning
5. M4 purchase_quantity_fluctuation_warning + new_terminal_detection
6. structured evidence bundle
7. detector cache / evidence timeline
8. LLM / MCP line-card generation
```

---

## 7. 当前阶段结论

M2/M3/M4 的共同原则是：

```text
概率模型负责估计风险；
业务排序负责决定处理优先级；
survival-lite 负责判断是否超出自身采购节奏；
detector 负责提供结构化证据；
LLM 后续只负责表达，不参与判断。
```

当前不应继续在主概率模型上做大规模调参。下一步更合理的是将 M1–M4 按此接口落地为可复用模块，并先在 reports 中生成 demo 级输出，不直接生产正式线索卡。