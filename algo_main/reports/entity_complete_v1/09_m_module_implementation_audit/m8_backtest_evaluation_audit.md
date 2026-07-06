# M8 回测、评估与验收协议审计

## 状态

`partially_implemented`，其中 Stage 1 scorer 评估为 `implemented_current`。

## 当前已实现

Stage 1 scorer：

- AUC
- PR-AUC
- PR-AUC gain
- ECE
- Brier
- LogLoss
- TopK Precision / Recall / Lift / NDCG

当前最佳主模型：

- `xgboost_small`
- AUC：0.8212
- PR-AUC gain：0.3315
- ECE：0.0228

M1/M-stage：

- candidate_count
- candidate_die_recall
- candidate_lift
- candidate positive rate
- M2 one-shot diagnostic metrics
- M3 survival state vs die rate
- M4 detector hit vs die rate
- M5 status distribution
- M7 sample completeness
- M8 full_universe 与 candidate_probability_top10 简版 backtest

## 未完成

- 当前链路没有完整 M2 repeat model evaluation。
- 当前链路没有完整 row-level M3/M4/M5/M7 backtest。
- 当前链路没有完整 candidate-level utility backtest。
- 真实客户 5-10 个流失终端 proof-case 回测未完成。
- 没有人工复核 acceptance rate。
- 没有客户可见服务验收。

## legacy 对照

旧链路有 candidate utility backtest、static proof-case cards、candidate-level diagnostics。但旧链路无法证明 full-universe recall，也不能直接作为新链路完成证据。

## 结论

M8 当前足以支撑内部算法诊断和领导阶段汇报，不足以支撑客户可见服务验收。

