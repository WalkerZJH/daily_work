# MVC 分层实施计划：候选对象排序主链路

## Phase 0：口径冻结与正式批次发布

当前状态：代码已冻结为全 recurring 候选池；新的 `2025-12/full-recurring-v1` Parquet 批次正在物化。

- 冻结 recurring 准入、实体键、H3/H6/H12、默认排序字段和 Top N 仅为展示截断的口径。
- 禁止 `risk_level`、`is_high_risk`、detector 命中、企业 cap、global cap 参与候选准入。
- 使用与 artifact 一致的 scikit-learn 1.7.2 环境生成版本化 batch；不得训练模型、覆盖或删除旧 batch。
- 验收：manifest 的 `full_recurring_count == persisted_recurring_count == risk_entities.parquet` 中 recurring 行数。

## Phase 1：Model 层

当前状态：implemented。

- `BoundedCandidateSelector` 持久化完整 recurring universe；旧多召回分数只保留排序/诊断作用。
- manifest 与 Parquet validation 执行双计数校验。
- 统一候选详情 evidence：规则版本、监测逻辑、事实值、阈值和命中说明。
- 验收：任一 recurring 对象不会因概率、风险等级、detector、Top N 或历史 cap 被排除。

## Phase 2：Controller 层

当前状态：implemented。

- 保留 `/api/v1/risk-entities`，请求参数为 `manufacturer_code, observation_date, horizon, sort_by, sort_order, page, page_size`。
- 返回 `items` 与 `pagination.page/page_size/total/total_pages`；`entities` 仅临时兼容。
- 排序仅支持月度 `risk_probability`、`involved_amount`、`loss_value`；`detector_score` 返回 422。
- 工作台复用同一排序服务，以 `page=1,page_size=top_n` 查询。
- 验收：分页不重复、不遗漏；列表第一页与首页排序一致；查询不重跑模型。

## Phase 3：View 层

当前状态：implemented。

- 工作台使用 draftQuery/appliedQuery，用户点击查询后才刷新；首页不展示 detector、风险来源或规则分。
- `clues.html` 的历史路由保留，但页面业务语义变为候选对象排序列表；只渲染当前页。
- 详情只接受正式候选对象 ID；显示月度结果、H3/H6/H12 和当前 observation_date 的 detector 证据。
- 前端主链路统一使用“医院 × 药品”，不使用产品线概念。
- 验收：无 detector 命中时详情正常；detector 不影响候选池、排序、概率或金额。

## Phase 4：边界与后续 P1

- 配送 detector：`blocked_by_data`，disabled、runtime false、customer false。
- SKU shrink：缺少产品线领域概念，disabled，不进入当前主链路。
- 价格：仅在正式 Parquet 确认真实价格、单位一致和窗口可追溯后，才可实现中性的 `purchase_price_level_shift` 与 `purchase_price_dispersion`；不实现因果性 `price_competition`。
- 不纳入：one-shot 接入、运营闭环、内部评估页、配送恢复、产品线/SKU、Prototype 清理。
