# 当前实现状态：候选对象排序主链路

审计日期：2026-07-14

## 2026-07-14 规则线索详情修正

`clues.html` 是规则巡检结果，不是候选对象排序列表。`clue-detail.html` 已支持两条互斥的只读链路：带 `riskEntityId`（或兼容 `id`）时读取月度候选详情；仅带 `clueId` 时读取单条 Daily Detector 规则线索。后者不读取或展示月度概率、H3/H6/H12、金额、候选排名或概率趋势，也不会创建风险实体。

## 执行摘要

当前业务语义已冻结为：完整查询参数 → 候选对象排序工作台（Top N）→ 候选对象排序列表（分页）→ 候选对象详情（月度结果与当前 observation_date detector 证据）。

代码主链路已实现并通过定向测试；旧 `risk_entity`、`is_high_risk`、`high_risk_detector_evidence` 是历史技术命名，不代表候选对象经过固定高风险阈值准入。现有 `2025-12/formal-v2-raw` 的 1,229 行是历史截断结果，不能被视为完整 recurring 候选池。新的 `full-recurring-v1` Parquet 批次正在以冻结 artifact 物化，未训练模型、未覆盖旧批次。

## 数据层

| 产物 | 状态 | 证据 |
|---|---|---|
| 月度候选排序结果 | partially_implemented | `data/project_result_batches/.../formal-v2-raw/risk_entities.parquet` 是历史截断批次；`risk_algorithm_core/candidate_selector.py` 已改为全 recurring 持久化 |
| 新 full-recurring 批次 | partially_implemented | `scripts/generate_multi_month_formal_batches.py --run-id full-recurring-v1` 写入版本化 batch；物化运行中 |
| Parquet-only 结果契约 | implemented | `risk_result_contracts/validation.py`、`risk_model_core/repositories.py` |
| 双计数校验 | implemented | manifest 的 `full_recurring_count`、`persisted_recurring_count` 与实际 Parquet recurring 行数必须一致 |
| detector 证据 | partially_implemented | 现有正式 batch 有 quantity/frequency 证据；IPI 正式 evidence 缺失需在新 batch 后复核 |

## Model 层

| 模块 | 状态 | 结论 |
|---|---|---|
| candidate_ranking_model | implemented | `BoundedCandidateSelector.select` 仅以 `candidate_type=recurring` 准入；旧 union/cap 仅保留兼容元数据 |
| candidate_pool_policy | obsolete_or_conflicting | `multi_recall_union_top10`、生产企业 50 条与 global 30,000 条为旧语义，不进入正式选择路径 |
| risk_entity_model | partially_implemented | 仍使用历史 `risk_entity` 名称；业务语义为候选排序结果 |
| horizon profile | implemented | H3/H6/H12 通过 `risk_entity_horizon_profiles.parquet` 关联 |
| detector evidence contract | implemented | `detector_result_service.py::_evidence_item` 返回版本、逻辑、事实值、决策阈值 |
| sku_shrink | blocked_by_missing_domain_concept | 当前主链路无产品线领域概念 |
| delivery detectors | blocked_by_data | catalog/config disabled；不执行、不展示、不归责 |
| causal price_competition | not_implemented | 不得生成竞品替代、低价归因或配送商责任结论 |

## Controller 层

| 模块 | 状态 | 证据 |
|---|---|---|
| candidate_ranking_api | implemented | `GET /api/v1/risk-entities` 接受 `manufacturer_code, observation_date, horizon, sort_by, sort_order, page, page_size` |
| API 分页 | implemented | 返回 `items`、`pagination.page/page_size/total/total_pages`；`entities` 为暂时兼容别名 |
| 排序边界 | implemented | 仅 `risk_probability`、`involved_amount`、`loss_value`；`detector_score` 返回 `422 SORT_METRIC_NOT_AVAILABLE` |
| workbench service reuse | implemented | 工作台以同一排序服务请求 `page=1,page_size=top_n` |
| detail scope | implemented | 详情仅按 `risk_entity_id` 从正式结果读取；前端 clue-only 旁路已删除 |

## View 层

| 模块 | 状态 | 结论 |
|---|---|---|
| 候选对象排序工作台 | implemented | `MonthlyWorkbenchView.vue` 使用草稿查询与查询按钮；不再请求 detector clues/status，不展示风险来源列 |
| 候选对象排序列表 | implemented | 月度候选排序属于 `index.html`，不由 `clues.html` 承担 |
| 候选对象详情 | implemented | `clue-detail.html` 的 candidate mode 接受候选对象 ID，显示月度结果、H3/H6/H12 和 detector 证据 |
| 首页风险来源列 | obsolete_or_conflicting | 所有对象来自月度候选排序，原列为常量语义，已从正式首页移除 |
| 规则线索独立主列表 | implemented | `clues.html` 是规则巡检结果；`clue-detail.html?clueId=` 展示 rule-only detector 事实证据，不进入月度候选链路 |

## 主链路完整性结论

**基本完整但存在正式数据断点。** 代码、API、分页、工作台、列表、详情和 detector 边界均已接通；只有新的正式 full-recurring Parquet 批次完成并验证后，才能宣布数据层主链路完整。当前旧批次不得作为“全部合格 recurring 候选对象”使用。
