# M2 One-shot high value 特殊方案审计

## 状态

`entity_complete_v1` 为 `partially_implemented`；旧链路 one-shot repeat model 为 `implemented_legacy_only`；复用 recurring scorer 为 `rejected_or_abandoned`。

## 当前 entity_complete_v1 证据

- `one_shot_first_purchase_features.parquet`：200,640 行，说明 first-purchase feature base 已存在。
- `m2_one_shot_metrics.csv`：只有诊断指标，没有独立 repeat model artifact。
- 当前 M2 诊断用现有 `probability_score` 对 one-shot alive/repeat 方向做评估，H3/H6/H12 AUC 约 0.30，PR-AUC gain 为负。

## legacy 证据

旧链路 `alive_prediction_one_shot_repeat_v1` 实现过：

- first-purchase samples：40,052
- H3/H6/H12 repeat model 均训练成功
- `repeat_probability_H`
- `one_shot_non_repeat_risk_H`
- retention_risk / conversion_opportunity / balanced_attention 三套策略
- group prior explanation
- KMeans similarity explanation deferred

但该结果属于旧链路，不能直接作为新链路完成证据。

## 设计对齐

已落地：

- 当前已有 first-purchase feature universe。
- 已验证 one-shot 不应解释为 recurring churn。
- auto dispatch / LLM 未介入。

未落地：

- 新链路下没有独立 `repeat_probability_H` 模型。
- 没有当前 `one_shot_attention_candidates_enriched`。
- 没有当前 `retention_risk / conversion_opportunity / balanced_attention` 三策略输出。
- 没有当前 one-shot structured explanations。

## 结论

M2 当前不能算 `implemented_current`。应明确放弃“复用 recurring churn scorer”路线，并在新链路下重建 first-purchase repeat propensity model。

