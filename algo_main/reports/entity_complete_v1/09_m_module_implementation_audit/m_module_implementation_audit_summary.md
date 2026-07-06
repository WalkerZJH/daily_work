# M0-M8 实现状态审计摘要

## 总体结论

当前不能说 M0-M8 全部完成。

更准确的说法是：`entity_complete_v1` 已经完成新口径下的数据重建、特征/标签、主 scorer、轻量 M-stage 诊断和基础验收报告；但 M1-M8 里相当一部分仍是旧 `alive_prediction` 链路原型、接口保留、样例输出或明确延后项。当前适合定位为内部诊断 / 分析师视图准备阶段，不适合对外宣称为客户可见正式概率服务。

## 当前阶段

- 新链路已落地：entity-complete / manufacturer-complete / choice-set 抽取，清洗后 `model_base` 693,596 行，51,536 个 entity，feature/label rows 1,183,902。
- 新链路主模型已落地：`xgboost_small` full-universe scorer，AUC 0.8212，PR-AUC gain 0.3315，ECE 0.0228。
- 新链路 M-stage 已轻量跑通：M1 候选、M2 one-shot 诊断、M3 interval 状态、M4 两个 detector evidence 指标、M5 状态分布、M7 500 行样例 bundle、M8 简版回测。
- 阻塞外部服务的关键问题：M1 平均 candidate die recall 约 0.1862；M2 one-shot 不能复用 recurring scorer；M4 detector catalog 未在新链路完整落地；M6 未实现；M7 不是正式线索卡；真实客户 5-10 个 proof-case 回测未完成。

## M0-M8 一句话状态

- M0：数据粒度、H3/H6/H12、概率语义隔离基本落地；三类对象表和展示去重只部分落地。
- M1：`entity_complete_v1` 中有 top10 候选策略和 recall/lift 指标，但不是设计中的 recurring/one-shot/demand-shape 三表闭环，也未实现 Top5% + manufacturer min-fill。
- M2：旧链路实现过 one-shot repeat propensity；新链路只有 one-shot 特征和复用当前 scorer 的诊断，结论是不能作为 one-shot 概率。
- M3：旧链路 survival-lite 完整度更高；新链路只落地 interval evidence 分布，复杂 survival / BG-NBD / Pareto-NBD 已删除或延后。
- M4：旧链路有 terminal/frequency/quantity/new-terminal detector 和 price/delivery interface；新链路只保留 interval/frequency 两个轻量 evidence 指标。
- M5：旧链路实现完整 candidate_status_decision；新链路只输出状态分布，`auto_dispatch_allowed=false` 保持成立。
- M6：设计明确为 interface-only/deferred，当前没有 cache/timeline 实现。
- M7：旧链路生成 structured evidence bundle；新链路只有 500 行样例原材料，不调用 LLM，不等于正式线索卡。
- M8：主模型指标、TopK、M1/M-stage 轻量指标已覆盖；真实客户 proof-case 和完整候选级验收仍未完成。

## entity_complete_v1 下真正跑通的模块

- M0 核心数据契约：entity grain、`drug_group_source=drug_code`、H3/H6/H12、`drug_category_code` 不当产品线。
- Stage 1 scorer 与评估：AUC / PR-AUC / ECE / Brier / LogLoss / TopK。
- M1 轻量候选策略：probability/interval/frequency/recency/hybrid top10。
- M3/M4 轻量 evidence：interval 状态、frequency/interval detector hit 分布。
- M5/M7/M8 轻量产物：状态分布、500 行 bundle sample、full-universe 与 candidate top10 回测摘要。

## 只有 legacy 旧结果的模块

- M2 one-shot repeat propensity 正式原型。
- M3 `survival_refinement_results` 级别 survival-lite 输出。
- M4 完整 detector evidence rows、interface-only price/delivery rows、new terminal detection。
- M5 完整 `candidate_status_decision.csv`。
- M7 完整 `structured_evidence_bundle.csv` 与 allowed/forbidden claims 明细。
- candidate-level utility backtest 与 static line-card sample。

这些旧结果因旧 `alive_prediction` 数据存在 row-level TOP N / entity 历史截断污染风险，只能作为 legacy exploratory evidence。

## 设计文档或接口保留

- M6 evidence cache / timeline。
- M1 三类对象表的标准命名与 entity-level `primary_horizon` 折叠。
- M4 price/delivery/SKU/wallet share 等 detector。
- M7 LLM line-card generation。
- M8 真实客户 proof-case 回测。

## 明确放弃或降级

- BG/NBD / Pareto-NBD / formal survival：v1 删除或延后，当前采用 survival-lite / interval evidence。
- supplier-switch / competitor-substitution：choice-set 只能作为 partial platform context，不能解释为完整市场替代。
- one-shot 复用 recurring churn scorer：新链路诊断显示不可用，应重建 one-shot repeat model。
- price detector：价格可比口径未确认，保持 interface-only。
- delivery detector：delivery_time / arrival_time 缺失或口径不足，当前跳过/interface-only。
- auto dispatch：明确禁止，`auto_dispatch_allowed=false`。
- customer-facing probability service：当前不建议。

## 下一步最值得做

P0 是 M1 candidate policy：先确认业务 TopN / 工作清单负载，再优化候选池 recall、manual review load 和三类对象表拆分。P1 是在 `entity_complete_v1` 下重建 M2 one-shot repeat propensity，并把 M3/M4 从轻量分布升级为可审计明细表。M6 cache 和 LLM line card 均不应优先于 M1/M2/M4 的新链路重跑。

## 对外完成度表述

不建议说“已完成 M0-M8 全流程”。建议说：

```text
已完成 entity_complete_v1 新数据链路、主 scorer 与 M-stage 内部诊断版审计。
M0 基本落地，M1/M3/M5/M7/M8 在新链路下为轻量或部分落地。
M2、完整 M4、完整 M5/M7 仍主要停留在旧链路原型，需要在 entity_complete_v1 下重建或重跑。
当前可支持内部诊断和分析师视图设计，不支持客户可见正式概率服务或自动派单。
```

