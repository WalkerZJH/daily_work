# M1 Stage 1.5 候选池生成与业务排序审计

## 状态

`partially_implemented`。

## 当前 entity_complete_v1 证据

- 代码：`algo_main/src/alg/tasks/die_prediction/entity_complete_rebuild.py`
- 产物：`algo_main/data/entity_complete_v1/07_candidates/m1_candidates.csv`
- 指标：`algo_main/reports/entity_complete_v1/04_m_stage_pipeline/m1_candidate_policy_metrics.csv`
- 摘要：`M1 mean candidate die recall: 0.1862`

当前候选策略包括：

- `probability_top10`
- `interval_top10`
- `frequency_top10`
- `recency_top10`
- `hybrid_top10`

按当前 CSV 聚合，`probability_top10` 平均 candidate die recall 约 0.2074，candidate lift 约 2.0736。这个结果有诊断价值，但 recall 仍有限。

## 与设计要求对齐

已实现：

- 按 `cutoff_month x horizon` 生成 Top pct 候选。
- 支持 H3/H6/H12 long score。
- 产出 candidate recall / lift / candidate_count 等指标。
- `business_priority_score` 没有反向污染概率模型。

未完整实现：

- 设计默认的 `global_top_pct=0.05` 没有落地；当前是 Top10。
- `manufacturer_min_fill` 没有在当前 M1 artifact 中落地。
- `recurring_business_priority_candidates_by_horizon` 和 entity-level `recurring_business_priority_candidates` 没有按设计命名输出。
- `primary_horizon`、`selected_horizons`、`rank_global`、`rank_within_manufacturer` 没有形成当前标准表。
- one-shot 和 demand-shape 当前没有作为正式 side tables 输出。
- `value_at_risk_H` / `business_priority_score_H` 缺少当前 artifact 标准字段。

## legacy 对照

旧链路有 M1/M2 audit 和 correction report，证明做过 side-table 语义检查、demand-shape display-ready 压缩、one-shot 旁路校验。但旧链路受历史抽样污染影响，只能作为参考。

## 结论

当前 M1 可支撑内部算法诊断，不能支撑客户可见工作清单。P0 应先确认业务可接受的 TopN / 每厂商最少候选 / 人工复核负载，再重做 M1 policy。

