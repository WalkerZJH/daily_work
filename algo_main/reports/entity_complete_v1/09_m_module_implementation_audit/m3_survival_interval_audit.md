# M3 Survival / Interval-aware 精查审计

## 状态

`partially_implemented`。

## 当前 entity_complete_v1 证据

当前新链路生成 `m3_survival_lite_metrics.csv`，按 horizon 与 interval 状态统计 die rate：

- `interval_unavailable`
- `not_overdue`
- `near_due`
- `overdue`

这些状态对 die rate 有区分力，说明 interval evidence 有效。

## 缺口

当前新链路没有生成设计要求的 row-level `survival_refinement_results`，缺少：

- `expected_interval_months`
- `expected_interval_source`
- `overdue_ratio`
- `overdue_gap_months`
- `survival_confidence`
- `history_sufficiency_flag` 的 M3 输出
- `demand_shape_route`
- `fallback_method`
- `human_review_required`

当前 M3 也没有严格限制只读取 `recurring_business_priority_candidates` 的正式三表输入，因为 M1 当前尚未输出该正式主表。

## legacy 对照

旧链路 `alive_prediction_survival_lite_v1` 生成过更完整 survival-lite：

- 1,354 个 recurring main candidates
- one-shot processed=false
- survival_state 分布
- expected_interval_source
- history_sufficiency_flag
- materially_overdue / likely_churn_interval 183 行

但旧链路仅为 legacy evidence。

## 放弃或延后项

设计文档明确 M3-v1 不采用 BG/NBD / Pareto-NBD。formal survival、Cox/AFT、discrete-time survival 当前均不实现，属于 `rejected_or_abandoned` 或 `intentionally_deferred`。

## 结论

当前 M3 是有效的 interval evidence 诊断，不是完整 survival 精查模块。下一步应在 M1 正式主候选表稳定后，把旧 survival-lite 逻辑重跑到 `entity_complete_v1`。

