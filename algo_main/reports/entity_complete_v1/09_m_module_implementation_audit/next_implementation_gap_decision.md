# Next Implementation Gap Decision

## 当前最缺什么

当前最缺的是候选池和业务配置，不是继续换模型。主 scorer 指标已经足够做内部诊断；真正阻塞客户可见的是 M1 recall / TopN / 人工负载 / 三类候选对象边界。

## P0

1. 优化 M1 candidate policy：
   - 与需求部门确认 TopN、Top pct、每 manufacturer 最少数量、每日/每周工作清单容量。
   - 在 `entity_complete_v1` 下输出三类正式表：recurring、one-shot、demand-shape。
   - 实现或明确替代 global Top5% + manufacturer min-fill。
   - 输出 entity-level `primary_horizon` 和 horizon-level audit 表。

2. 做真实业务 proof-case 需求确认：
   - 让业务提供 5-10 个客户确认流失终端和正常对照。
   - 对齐产品线口径、订单粒度、真实停购口径。

## P1

1. 重建 M2 one-shot repeat propensity：
   - 不复用 recurring scorer。
   - 基于 `one_shot_first_purchase_features.parquet` 建 H3/H6/H12 repeat model。
   - 输出三套 attention policy，并标注 repeat_probability 不是 recurring churn。

2. 把 M3/M4/M5/M7 从 summary 升级为 row-level：
   - M3：`survival_refinement_results`
   - M4：`detector_evidence_results`
   - M5：`candidate_status_decision`
   - M7：`structured_evidence_bundle`

## P2

1. M4 detector 重跑与补齐：
   - 优先 interval overdue 与 frequency decay row-level detectors。
   - quantity fluctuation 可在 numeric reliability guardrail 后重跑。
   - price/delivery 暂不补，除非数据口径确认。

2. 扩大 manufacturer / entity / choice-set coverage：
   - 这是进入客户可见服务前的必要条件。
   - 当前 extract 是 selected manufacturers/entities，不是 full SQL universe。

## P3

1. M6 cache/timeline：
   - 暂不优先开发。
   - 等 M4 row-level detector schema 稳定后再做。

2. LLM line card：
   - 暂不优先开发。
   - 等 M7 full bundle 和人工 sample review 通过后再进入。

3. 前端/客户可见服务：
   - 当前不应进入客户可见正式服务。
   - 可做内部诊断/分析师 demo 设计，不做生产实现。

## 前后端展示 demo 设计建议

仅建议，不执行实现：

- 后端 demo 只读 `reports/entity_complete_v1` 与 `data/entity_complete_v1` 的已生成静态产物，不连接 SQL、不训练、不派单。
- 提供一个“内部诊断视图”接口层，按 module 输出：M0 契约状态、M1 candidate policy 对比、M2 one-shot 失败诊断、M3 interval state、M4 evidence hit、M5 status 分布、M7 sample bundle、M8 metrics。
- 前端第一屏不要做营销页，应是分析师工作台：左侧筛选 manufacturer / horizon / cutoff，主区展示 candidate policy recall/lift、状态分布、样例 evidence bundle。
- 明确展示语义边界：概率只显示 `churn_probability` 或 `repeat_probability`；business priority、detector hit、survival state 用“证据/排序/状态”标签，不用概率样式。
- 所有卡片默认带 caveat：internal diagnostic only、auto dispatch false、not customer-facing probability service。
- demo 中不要生成正式线索卡，只展示 structured evidence bundle 原材料和 allowed/forbidden claims。

## 对领导汇报的完成度表述

建议表述为：

```text
M0 和新数据链路已基本完成；主 scorer 已在 entity_complete_v1 上跑通并达到内部诊断可用。
M1-M8 已有轻量诊断闭环，但 M2、完整 M4/M5/M7 仍需要从旧链路迁移到 entity_complete_v1。
当前阶段适合内部诊断和分析师视图，不适合客户可见概率服务或自动派单。
下一步 P0 是候选池策略与业务工作清单配置，不是继续盲目调模型。
```

