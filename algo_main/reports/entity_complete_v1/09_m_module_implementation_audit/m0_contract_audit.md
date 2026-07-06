# M0 数据与接口总契约审计

## 状态

`implemented_current` 为主，三类对象表和展示去重为 `partially_implemented`。

## 已落地

- entity 粒度：`manufacturer_code x hospital_code x drug_group`，当前 `drug_group_source=drug_code`，实际等价于 `manufacturer_code x hospital_code x drug_code`。
- `drug_category_code` 只作为分类/分层/特征维度，清洗报告明确不能当 `product_line_code`。
- H3/H6/H12 均保留：`alive_labels_H3_H6_H12.parquet` 有 H3/H6/H12 alive/die/window_closed 字段。
- 新链路特征和预测产物保留主键：`manufacturer_code`、`hospital_code`、`drug_group`、`drug_group_source`、`cutoff_month`、`horizon`。
- 概率语义隔离基本落地：模型选择报告明确 value/business priority 不进概率特征；detector severity、business priority、one-shot attention 不应解释为概率。
- choice-set context 已加入，但被标注为 partial platform context，不能解释为完整市场份额或竞品替代。

## 部分落地或缺口

- M0 要求三类对象表：`recurring_business_priority_candidate`、`one_shot_attention`、`demand_shape_observation`。新链路当前主要是统一的 `m1_candidates.csv` 与 `one_shot_first_purchase_features.parquet`，没有正式拆成三张当前链路对象表。
- 展示去重规则 `business_priority > demand_shape_observation > one_shot_attention` 旧链路做过 display-ready 压缩，新链路没有对应正式产物。
- `business_priority_score_H` / `value_at_risk_H` 在当前 M1 主 artifact 中不是标准字段，仍需要作为后处理补齐。

## 语义风险

当前最大风险不是主 scorer，而是下游展示：如果前端直接展示 `m1_candidates.csv` 的 `candidate_policy` 或 `m4_detector_evidence_metrics.csv` 的 hit rate，容易把 business priority、detector severity、one-shot attention 或 interval evidence 误写成概率。

## 结论

M0 核心契约可认为已在 `entity_complete_v1` 基本落地，但对象表拆分和展示去重仍需按 M1/M7 输出补齐。

