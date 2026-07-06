# Legacy vs Entity Complete Gap

## 旧 alive_prediction 链路

旧链路实现过较多 M1-M8 原型：

- M1/M2 side-table audit 与 correction
- M2 one-shot repeat propensity
- M3 survival-lite row-level refinement
- M4 detector evidence rows
- M5 candidate_status_decision
- M7 structured_evidence_bundle
- static line-card sample
- candidate utility backtest

但旧链路存在历史抽样和 entity 历史截断风险，旧结果只能作为 exploratory / legacy。

## 新 entity_complete_v1 链路

新链路已重新跑通：

- SQL sampling integrity 修正与 entity/manufacturer/choice-set extraction
- 清洗、事实、feature/label
- Stage 1 scorer 与模型评估
- M-stage 轻量诊断：M1/M2/M3/M4/M5/M7/M8 summary-level outputs

新链路仍未重跑：

- M1 三类正式对象表
- M2 independent repeat propensity model
- M3 row-level survival_refinement_results
- M4 full detector_evidence_results
- M5 full candidate_status_decision
- M7 full structured_evidence_bundle
- M8 candidate utility/proof-case 回测

## 关键差异

| 模块 | legacy | entity_complete_v1 |
|---|---|---|
| M0 | 旧口径不可靠 | 新口径基本落地 |
| M1 | side-table audit 完整些 | unified top10 candidates，recall 有限 |
| M2 | repeat model 已实现 | 只有 one-shot feature 和失败诊断 |
| M3 | row-level survival-lite | aggregate interval state metrics |
| M4 | row-level detector catalog | aggregate frequency/interval hits |
| M5 | full candidate_status_decision | status distribution only |
| M6 | interface fields only | interface/deferred |
| M7 | full bundle | 500 行 sample |
| M8 | candidate-level legacy backtest | full-universe scorer metrics + 简版 M8 |

## 结论

当前项目已经从旧污染样本迁移到新链路，但并没有把旧链路 M2-M7 的完整原型全部迁移完成。阶段汇报必须区分“旧链路实现过”和“新链路已重跑”。

