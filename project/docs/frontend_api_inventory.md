# Project Backend API Inventory

本文档给前端作为接口调用清单，避免误请求不存在的路径导致 404，或绕过
Project API 触发本地 fallback。前端只能调用 Project 后端，不直接读取
`risk_model_core`、result-batch 文件或 `algo_main`。

## 环境与日期语义

正式多月结果使用：

```text
RISK_RESULT_BATCH_ROOT=C:\Users\admin\Myprojects\for_git\algo_main\data\entity_complete_v2_coverage_expansion\16_multi_month_formal_result_batches
```

如同时存在 `RISK_RESULT_BATCH_ROOT` 和 `RISK_RESULT_BATCH_DIR`，后端优先使用
`RISK_RESULT_BATCH_ROOT`。`RISK_RESULT_BATCH_DIR` 只作为 legacy single batch 兼容。

当前日期语义：

- `observation_date`：用户查看的日报日期。
- `probability_report_month`：该观察日期之前最近一个完整自然月。
- `detector_run_date`：规则巡检日期，等于 observation date。
- `context_status`：`ready`、`detector_run_unavailable`、`probability_month_unavailable`、`no_available_context` 等。

示例：

```text
observation_date=2025-12-05
probability_report_month=2025-11
detector_run_date=2025-12-05
context_status=detector_run_unavailable
```

这不是 latest fallback，而是观察日期解析。

## 可用前端 API

### `GET /api/v1/report-context`

用途：先解析观察日期上下文，或由页面 API 内嵌 `report_context`。

Query:

- `observation_date`
- `report_month`
- `run_date`，旧兼容参数，等价映射到 `observation_date`
- `horizon`
- `manufacturer_code`
- `user_id`

核心返回：

- `ready`
- `observation_date`
- `probability_report_month`
- `probability_batch_id`
- `probability_batch_available`
- `detector_run_date`
- `detector_run_id`
- `detector_run_available`
- `context_status`
- `manual_selection_required`
- `available_report_months`
- `available_detector_run_dates`
- `requested_horizon`
- `effective_horizon`
- `warnings`
- `caveats`

### `GET /api/v1/my/manufacturers`

用途：生产企业选择器。后端按用户 scope 或 batch fallback 返回可见企业。

Query:

- `observation_date`
- `report_month`
- `run_date`
- `horizon`
- `manufacturer_code`
- `user_id`

### `GET /api/v1/workbench`

用途：首页工作台。前端主入口。

Query:

- `observation_date`
- `manufacturer_code`
- `report_month`
- `run_date`
- `horizon=H3|H6|H12`
- `top_n`
- `sort_by=loss_value|risk_probability|detector_score|involved_amount`
- `user_id`

返回包含：

- `report_context`
- `today_focus`
- `daily_detector_summary`
- `top_rule_clues`
- `risk_entities`
- `rows`，兼容旧页面

规则：

- 风险概率、金额、展示名使用 `probability_report_month` 对应 batch。
- 日报规则线索使用 `detector_run_date`。
- `detector_run_available=false` 时，仍可返回月报风险对象，但 `daily_detector_summary.ready=false` 且 `top_rule_clues=[]`。
- 不返回 `fill_policy`、`business_score`、模型指标、mock 线索。

### `GET /api/v1/risk-entities`

用途：月报风险对象列表。

Query:

- `observation_date`
- `manufacturer_code`
- `report_month`
- `run_date`
- `horizon`
- `top_n`
- `sort_by`
- `user_id`

不要把非月报高风险的规则线索混入该列表；全部规则线索使用
`/api/v1/daily-detector/clues`。

### `GET /api/v1/risk-entities/{risk_entity_id}`

用途：风险对象详情。

Query:

- `observation_date`
- `report_month`
- `run_date`
- `horizon`
- `manufacturer_code`
- `user_id`

### `GET /api/v1/risk-entities/{risk_entity_id}/probability-trend`

用途：概率和涉及金额趋势。

Query:

- `observation_date`
- `report_month`
- `run_date`
- `horizon`
- `manufacturer_code`
- `user_id`

### `GET /api/v1/daily-detector/status`

用途：日报规则巡检状态。

Query:

- `observation_date`
- `report_month`
- `run_date`
- `horizon`
- `manufacturer_code`
- `user_id`

若 `detector_run_available=false`，返回 `200`、`ready=false`、`context_status=detector_run_unavailable`，不 mock。

### `GET /api/v1/daily-detector/clues`

用途：全部规则线索页。

Query:

- `observation_date`
- `manufacturer_code`
- `report_month`
- `run_date`
- `horizon`
- `top_n`
- `sort_by=detector_score`
- `detector_family`
- `detector_id`
- `only_monthly_high_risk`
- `page`
- `page_size`

返回分页后的 `items`/`clues`，不要在首页请求全量。

### `GET /api/v1/detectors/catalog`

用途：规则能力目录。可展示 implemented / interface_only / experimental / reserved 状态。

### `GET /api/v1/detectors/runs`

用途：规则巡检 run 列表。

Query:

- `report_month`
- `run_date`
- `limit`

### `GET /api/v1/detectors/clues`

用途：兼容的规则线索查询入口。新页面优先使用 `/api/v1/daily-detector/clues`。

### `GET /api/v1/risk-entities/{risk_entity_id}/detector-evidence`

用途：风险详情页的附着规则证据。

Query:

- `observation_date`
- `report_month`
- `run_date`
- `horizon`
- `detector_family`
- `detector_id`

不存在的 risk entity 返回 404；不要用 daily clue 创建风险详情。

### `GET /api/v1/display-lookup/status`

用途：展示名映射状态。

Query:

- `observation_date`
- `report_month`
- `run_date`
- `horizon`
- `manufacturer_code`
- `user_id`

### `GET /api/v1/detectors/config-status`

用途：内部配置状态提示。业务前端只展示“参数下次巡检生效”提示，不展示完整超参数。

### `GET /api/v1/runtime-profile`

用途：内部 diagnostics，查看运行耗时。

Query:

- `report_month`

返回 `monthly_probability_total_seconds`、`detector_total_seconds`、
`end_to_end_seconds` 等内部字段。不要在客户首页展示。

## 兼容或废弃 API

### `GET /api/risk/my/top-entities`

旧 TopEntity 入口。当前页面优先使用 `/api/v1/workbench` 和
`/api/v1/risk-entities`。保留用于后端策略验证。

### `GET /api/v1/daily-detector/dates`

旧日期选择器入口。Observation context 下前端优先调用 `/api/v1/report-context`。

### `GET /api/v1/oneshot-terminals`

旧 one-shot 页面入口。客户侧不要把 one-shot 称为模型高风险。

### `GET /api/v1/monthly-reports`

旧月报 payload 入口。新前端主流程不应依赖。

### `GET /api/v1/proof-cases`

旧 proof case payload 入口。正式模式不得伪造 proof case。

## 内部、调试、历史 API

以下 `/api/v0/*` 不是客户前端正式数据链路，除非明确做内部工具页：

- `GET /api/v0/detectors/catalog`
- `POST /api/v0/detectors/run`
- `GET /api/v0/detectors/config`
- `GET /api/v0/detectors/{detector_id}/config`
- `PATCH /api/v0/detectors/{detector_id}/config`
- `POST /api/v0/detectors/{detector_id}/run`
- `POST /api/v0/detectors/run-by-category`
- `GET /api/v0/config`
- `GET /api/v0/config/effective`
- `POST /api/v0/config/dry-run`
- `GET /api/v0/options/enterprises`
- `GET /api/v0/options/provinces`
- `GET /api/v0/options/product-lines`
- `GET /api/v0/options/detector-categories`
- `GET /api/v0/options/detectors`
- `POST /api/v0/debug/data-quality`
- `GET /api/v0/debug/unit/{org_code}/{product_line_code}`
- `GET /api/v0/debug/features/{org_code}/{analysis_grain}/{target_code}`
- `POST /api/v0/debug/preprocess/run`
- `GET /api/v0/debug/detectors`
- `GET /api/v0/debug/unit/{org_code}/{analysis_grain}/{target_code}`
- `POST /api/v0/inspection/dry-run`
- `POST /api/v0/backtest/walk-forward`
- `GET /api/v0/backbone/palive/config`
- `PATCH /api/v0/backbone/palive/config`
- `POST /api/v0/backbone/palive/experiment`
- `POST /api/v0/backbone/predict`
- `POST /api/v0/smoke-test/database`
- `POST /api/v0/smoke-test/freshness`
- `POST /api/v0/training/build-dataset`
- `GET /api/v0/users/me/config`
- `PATCH /api/v0/users/{user_id}/preferences`

这些接口可能读取旧配置、debug service、数据库 smoke test 或运行型 detector；
正式风险页面不得依赖它们。

## 预留待实现

- 真实用户权限系统替换 batch manufacturer fallback。
- 规则参数编辑 API 的 pending/effective 双版本写入。
- Result DB table repository 替换 parquet/csv result-batch。
- 客户侧可配置的 observation date selector 后端策略扩展。
