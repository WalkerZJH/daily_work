# API

## Frontend Page API v1

这些接口供 Vue 页面读取稳定页面数据，前端不直接组合调用 `/api/v0/backbone` 或 `/api/v0/detectors`。第二层算法抽离完成后，后端只需要让结果批次或 `risk_model_core` payload 按以下字段供数，前端链路无需改动。

- `GET /api/v1/workbench`：返回生产商视角的医院 × 药品主工作台，`rows` 固定按 `business_score` 降序。`business_score = risk_probability * average_consumption_in_window`。当 global 当月数量不足时，后端直接补齐到 `fill_policy.workbench_target_count = 20`。
- `GET /api/v1/risk-entities`：返回风险实体清单，核心字段包括 `entity_id`、`hospital_name`、`drug_name`、`manufacturer_code`、`horizon`、`risk_probability`、`average_consumption_in_window`、`business_score`、`risk_band`、`risk_card_count`、`primary_reason`。
- `GET /api/v1/risk-entities/{entity_id}`：返回详情页数据，`horizon_profiles` 至少覆盖 `H3`、`H6`、`H12`；每个 horizon 包含 `detector_results`、`xgboost_shap`、`detector_narrative`。
- `GET /api/v1/oneshot-terminals`：返回新进终端监测数据，核心字段包括 `oneshot_count`、`repurchase_propensity`、`expected_repurchase_amount`、`priority`、`reason`。
- `GET /api/v1/monthly-reports`：返回往期日报切换、月报列表和批次上下文。
- `GET /api/v1/proof-cases`：返回成功案例列表。

页面批次上下文字段统一为 `report_month`、`score_as_of_date`、`data_watermark_at`、`score_batch_id`、`result_batch_id`、`primary_horizon`、`primary_horizon_label`。当前实现由 `risk_model_core.page_payload_builder` 提供确定性默认 payload；配置 `RISK_RESULT_BATCH_DIR` 后可读取结果批次中的页面 payload。

当前服务对外语义为 `supply_chain_order_risk_algo_backend`，API 前缀为 `/api/v0`。代码中若仍出现 `terminal_guard_algo_backend`，仅作为 legacy name 兼容。

`GET /api/v1/workbench` 与 `GET /api/v1/monthly-reports` 均返回 `model_metrics`。主干模型和所有可输出具体结果的模型都需要提供关键指标，至少包括 `auc`、`prauc`、`ece`、`brier`、`topk_recall`。

`topk_recall` 必须同时提供：

- `requested_k_percent`：请求的 TopK 占比，例如 0.10。
- `actual_k_percent`：实际评估占比，必须等于 `selected_count / evaluation_population` 四位小数回填。
- `selected_count`：实际入选样本数。
- `evaluation_population`：评估分母。
- `true_positive_count`：TopK 命中真实风险数。
- `recall`：`true_positive_count / positive_count` 的召回结果。
- `k_policy`：`direct_actual_share` 或 `union_backfilled_actual_share`。

如果多模型 union 后再计算 TopK recall，页面和 API 均使用 union 之后的实际占比作为 K。例如请求 Top 10%，union 后覆盖 12.8%，则 `requested_k_percent=0.10`、`actual_k_percent=0.1280`、`k_policy=union_backfilled_actual_share`。

## 主干算法 smoke test

`POST /api/v0/smoke-test/database`

用于真实数据库小窗口链路验证。接口读取同一个受限数据切口，构建 canonical orders、有效订单、分析单元、特征快照，并输出 P_alive 候选预览。

请求体：

```json
{
  "source_type": "database",
  "as_of_date": "2026-06-25",
  "lookback_days": 30,
  "baseline_days": 180,
  "history_start_date": null,
  "enterprise_code": null,
  "enterprise_name": null,
  "province_code": null,
  "province_name": null,
  "product_line_code": null,
  "row_limit": 500,
  "include_debug_features": false
}
```

响应重点字段：

```json
{
  "summary": {
    "source_type": "database",
    "table": "BS_Agent_DingDan",
    "as_of_date": "2026-06-25",
    "history_start_date": null,
    "lookback_days": 30,
    "baseline_days": 180,
    "raw_order_rows": 500,
    "effective_order_rows": 500,
    "analysis_unit_count": 455,
    "prediction_count": 455,
    "feature_column_count": 48,
    "model_name": "palive_interval_proxy",
    "model_version": "builtin",
    "fallback_used": true,
    "warnings": ["FALLBACK_INTERVAL_PROXY_USED"]
  },
  "palive_preview": [],
  "warning_summary": {}
}
```

口径说明：

- `raw_order_rows`：本次请求同一数据切口下进入 canonical 后、过滤有效采购前的订单行数。
- `effective_order_rows`：经过有效采购规则过滤后的订单行数。
- `analysis_unit_count`：有效订单中唯一 `org_code × product_line_code` 数量，不应超过 `effective_order_rows`。
- `prediction_count`：返回的 `BackbonePrediction` 条数，必须等于 `analysis_unit_count`。
- `feature_column_count`：特征快照表的列数，不是预测次数，也不是单元格数量。
- `include_debug_features=false` 时默认只返回关键调试字段；需要完整特征时显式传 `true`。

若 `analysis_unit_count > effective_order_rows` 或 `prediction_count != analysis_unit_count`，接口返回 `BACKBONE_UNIT_COUNT_INCONSISTENT` warning。

## 主干预测

`POST /api/v0/backbone/predict`

请求字段与 smoke test 对齐，返回：

```json
{
  "summary": {},
  "predictions": [],
  "warning_summary": {}
}
```

训练集构建可以使用多个历史 `origin_date`；`/api/v0/backbone/predict` 只能表示单个 `as_of_date` 的当前预测。对同一检测日，每个 `org_code × product_line_code` 只输出 1 条 P_alive 候选结果。模型缺失时 fallback 到 `palive_interval_proxy`，并通过 warnings 标明。

## Detector 目录

`GET /api/v0/detectors/catalog`

返回所有 detector 元数据，包括 `detector_id`、`name_zh`、`category`、`status`、`required_fields`、`optional_fields`、`required_features`、`implemented`、`enabled_by_default` 和 `notes`。

业务 category 固定为：

- `price_warning`
- `delivery_response`
- `terminal_change`
- `sales_fluctuation`
- `common_preprocess`

## Detector 配置

- `GET /api/v0/detectors/config`
- `GET /api/v0/detectors/{detector_id}/config`
- `PATCH /api/v0/detectors/{detector_id}/config`

所有阈值必须从 `DetectorRuntimeConfig` 读取，不允许在前端硬编码。`auto_baseline`、`ml_first`、`dl_first` 的启用状态、执行路径和结果状态由后端配置与响应字段明确给出。

## Detector 推理

- `POST /api/v0/detectors/run`
- `POST /api/v0/detectors/{detector_id}/run`
- `POST /api/v0/detectors/run-by-category`

输出 `DetectorEvidence` / `DetectorRunResult`，包含 `hit`、`severity`、`confidence`、`reason_code`、`metrics`、`evidence_items`、`warnings`、`sample_order_ids`、`statistics` 和后端生成的中文 `narrative`。

## Options

- `GET /api/v0/options/enterprises`
- `GET /api/v0/options/provinces`
- `GET /api/v0/options/product-lines`
- `GET /api/v0/options/detector-categories`
- `GET /api/v0/options/detectors?category=...`

health 页面应通过 options API 填充企业、省份、产品线和 detector 下拉选项，不要求用户手输 code。

## Inspection dry-run

`POST /api/v0/inspection/dry-run`

保持兼容 CSV 和 database 数据源。输出 `RiskCardCandidate` 草稿，必须包含 `backbone`、`detector_evidence`、`related_entities`、`warnings` 和 `debug_trace_id`。`risk_score_deprecated` 或 `rule_score` 只用于排序参考，不得解释为概率。

## 数据新鲜度

`POST /api/v0/smoke-test/freshness`

仅报告当前数据库窗口的 `max_order_time`、`row_count` 等信息。v0 不实现自动调度、自动重训或持久化 last_check。
