# API

当前服务对外语义为 `supply_chain_order_risk_algo_backend`，API 前缀为 `/api/v0`。代码中若仍出现 `terminal_guard_algo_backend`，仅作为 legacy name 兼容。

当前阶段是算法验证阶段：P_alive、主干风险分、DetectorEvidence、RiskCardCandidate 都是实验候选输出，不是正式业务工单，也不是已校准概率。

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

所有阈值必须从 `DetectorRuntimeConfig` 读取，不允许在前端硬编码。`auto_baseline` 仅用于测试和算法验证；`ml_first`、`dl_first` 当前只预留接口，未实现时返回 warning 并 fallback。

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
