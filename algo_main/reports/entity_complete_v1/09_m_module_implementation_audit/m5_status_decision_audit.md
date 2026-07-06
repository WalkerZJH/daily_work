# M5 证据融合与风险状态决策审计

## 状态

`partially_implemented`。

## 当前 entity_complete_v1 证据

当前 `m5_status_distribution.csv` 有：

- `low_confidence_watch`：345,643
- `manual_review`：95,628
- `observation_only`：226,940
- `priority_review`：41,619
- `auto_dispatch_allowed=False` 全量保持

这说明当前已做轻量状态规则，但产物是分布表，不是设计要求的 row-level `candidate_status_decision`。

## legacy 证据

旧链路 `alive_prediction_status_decision_v1` 生成过完整 `candidate_status_decision.csv`：

- recurring input rows：1,354
- one-shot input rows：1,692
- demand-shape display-ready rows：200
- total status decision rows：3,246
- final status 覆盖 priority_review / manual_review / observation_only / low_confidence_watch / one_shot_attention
- review_priority 覆盖 P1/P2/P3
- evidence_strength 覆盖 insufficient/weak/medium
- auto_dispatch_allowed all false

## 缺口

新链路缺少：

- row-level `candidate_status_decision`
- `final_candidate_status` 的完整枚举，尤其 `one_shot_attention` 和 `not_actionable`
- `review_priority` P0/P1/P2/P3
- `evidence_strength`
- detector hit count / strong detector hit count
- M6 timeline reserved fields

## 结论

M5 当前只适合做内部 M-stage 分布诊断。应在 M1/M2/M3/M4 当前链路明细表齐备后，再重跑完整 M5。

