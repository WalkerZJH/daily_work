# API

## Frontend Page API v1

这些接口是前端的唯一正式数据源。前端不直接读取 `risk_result_batch` 文件，不直接调用 `risk_model_core`，不从 `algo_main` 静态文件取映射，也不自行做用户 scope、排序或裁剪。

正式链路为：

```text
front_end -> project API -> risk_model_core -> risk_result_batch
```

客户页面 API 不暴露 `loss_value`、`monthly_loss_value`、`business_score`、`expected_loss` 或 `model_metrics`。内部评估指标可以保留在算法报告或 internal service 中，但不作为当前客户工作台 payload 的必需字段。

### Workbench

`GET /api/v1/workbench`

查询参数：

- `manufacturer_code`：可重复传入；后端会与当前用户可见 scope 取交集，不能越权。
- `report_month`：可选；用于选择月度风险清单。
- `run_date`：可选；用于选择每日 detector 巡检结果，不代表月度模型概率每日重算。
- `horizon`：`H3`、`H6`、`H12`，默认 `H6`。
- `top_n`：动态参数，默认 20，最小 1，最大 100。
- `sort_by`：`risk_probability` 或 `involved_amount`，默认 `risk_probability`。
- `X-User-Id` header：当前用户标识；默认 `admin`。

语义：

- 月度风险清单按 `report_month + horizon + manufacturer_code + top_n + sort_by` 获取。
- 每日巡检按 `run_date + manufacturer_code` 获取 detector 摘要。
- `risk_probability` 是月报模型概率，不随 `run_date` 每日变化。
- `involved_amount` 是所选 horizon 窗口内涉及金额，不是全历史金额。
- detector 只作为规则巡检线索和证据摘要，`detector_score` 不是概率。

返回重点字段：

```json
{
  "batch_context": {
    "report_month": "2025-12",
    "result_batch_id": "risk_result_batch_monthly_v2",
    "primary_horizon": "H6",
    "involved_amount_definition": "selected horizon window consumption"
  },
  "scope": {
    "manufacturer_count": 2,
    "manufacturer_codes": ["M1", "M2"]
  },
  "query": {
    "horizon": "H6",
    "top_n": 20,
    "sort_by": "risk_probability"
  },
  "detector_summary": {
    "detector_clue_count": 12,
    "latest_detector_run_date": "2026-07-09",
    "detector_status_summary": "ready"
  },
  "rows": [
    {
      "entity_id": "RE-001",
      "risk_entity_id": "RE-001",
      "manufacturer_code": "M1",
      "horizon": "H6",
      "risk_probability": 0.82,
      "involved_amount": 128000.0,
      "involved_amount_source": "selected_horizon_profile",
      "risk_band": "high",
      "primary_reason": "purchase interval overdue"
    }
  ]
}
```

### Risk Entity List

`GET /api/v1/risk-entities`

查询参数与 `/api/v1/workbench` 对齐：`manufacturer_code`、`report_month`、`horizon`、`top_n`、`sort_by`、`X-User-Id`。该接口复用 TopEntity service 的用户 scope、horizon profile 和排序逻辑。

返回列表字段包括 `entity_id`、`risk_entity_id`、`manufacturer_code`、`hospital_name`、`drug_name`、`horizon`、`risk_probability`、`involved_amount`、`involved_amount_source`、`risk_band`、`risk_card_count`、`primary_reason`。不返回 `business_score`、`loss_value` 或 `expected_loss`。

### Risk Entity Detail

`GET /api/v1/risk-entities/{entity_id}?horizon=H6`

返回已有月度风险实体详情。`selected_horizon_profile` 表示当前 horizon 的同口径字段：

- `horizon`
- `risk_probability`
- `involved_amount`
- `involved_amount_source`
- `risk_level` / `risk_band`
- `main_reason_summary`
- `detector_evidence_count`
- `updated_at`

详情页不会因为每日 detector clue 创建新的风险实体。

### Probability Trend

`GET /api/v1/risk-entities/{entity_id}/probability-trend?horizon=H6`

按同一 horizon 聚合返回历史月报趋势：

```json
{
  "risk_entity_id": "RE-001",
  "horizon": "H6",
  "items": [
    {
      "report_month": "2025-10",
      "horizon": "H6",
      "risk_probability": 0.71,
      "involved_amount": 98000.0
    }
  ]
}
```

### Current User Manufacturer Options

`GET /api/v1/my/manufacturers`

查询参数：

- `report_month`：可选。
- `manufacturer_code`：可选，可重复传入；非管理员只返回当前用户 scope 的交集。
- `X-User-Id` header：当前用户标识。

返回字段包括 `user_id`、`manufacturer_count`、`manufacturers[].manufacturer_code`、`manufacturers[].manufacturer_display_name`。

### Daily Detector Dates

`GET /api/v1/daily-detector/dates`

查询参数：

- `report_month`：可选。
- `limit`：默认 100，范围 1 到 500。

返回可选日报日期及巡检状态，字段包括 `run_date`、`report_month`、`detector_run_id`、`detector_config_version`、`clue_count`、`attached_high_risk_count`。该接口只说明每日规则巡检批次，不暗示月度模型概率每日变化。

## User Scoped Top Entity API

`GET /api/risk/my/top-entities`

用于后端按当前用户可见的生产商范围动态生成 TopEntity 列表。默认策略是：后端解析当前用户可见的 `manufacturer_code` scope，过滤 `risk_entities`，把全部可见 entity 合并后按选定排序策略排序一次，再返回总量不超过 `top_n` 的列表。默认不是每个生产商各取 `top_n`。

该接口只从 `risk_model_core` repository 读取 `risk_result_batch`，不读取 raw/source 业务库，不重跑主干模型、detector 或算法实验链路，不依赖 `algo_main`。前端不得直接读取 result batch，也不得自行做权限过滤或排序裁剪。

请求通过 `X-User-Id` header 识别当前用户，默认 `admin`。非管理员用户的 manufacturer scope 来自 `config/user_manufacturer_scope.example.csv`；管理员默认可查看当前 batch 中全部 manufacturer，也可通过 `manufacturer_codes` 参数指定范围。

参数：

- `report_month`：可选，默认 latest。
- `horizon`：默认 `H6`。
- `top_n`：动态参数，默认 20，最小 1。
- `max_n`：默认 50，`top_n > max_n` 时后端 clamp 并返回 warning。
- `group_by`：`user_scope` 或 `manufacturer`，默认 `user_scope`。`manufacturer` 保留为 deprecated/internal-only，用于后续企业均衡覆盖分析。
- `ranking_strategy`：`probability`、`involved_amount`、`mixed_v2`、`business_priority`、`interval`、`frequency`，默认 `probability`。页面 API 的 `sort_by=risk_probability` 会映射为 `probability`，`sort_by=involved_amount` 会映射为 `involved_amount`。`mixed_v2` 保留为 deprecated/internal-only；缺少 interval/frequency/business priority 字段时返回明确 warning，并设置 `ranking_strategy_effective=probability`。
- `candidate_type`：`recurring`、`one_shot`、`observation`、`all`，默认 `recurring`。
- `probability_threshold`：可选，0 到 1；deprecated/internal-only，不是默认策略。
- `include_threshold_overflow`：默认 `false`；deprecated/internal-only，不是默认策略。
- `fill_policy`：`none`、`observation_fill`、`one_shot_fill`，默认 `none`。默认不补齐，不伪造高风险。
- `manufacturer_codes`：可选；非管理员只能取自身 scope 的交集，不能越权。

页面级 API 优先复用该 service 的后端排序与权限逻辑。当前 `/api/v1/risk-entities` 会先通过 TopEntity service 获取用户可见 TopN；如果没有配置 result batch 或没有可返回实体，则回退到既有页面 payload。前端仍只调用页面 API，不需要理解 result batch、用户 scope 或排序细节。

返回重点字段：

```json
{
  "user_id": "js_manager_001",
  "report_month": "2025-12",
  "horizon": "H6",
  "ranking_strategy": "probability",
  "effective_ranking_strategy": "probability",
  "ranking_strategy_effective": "probability",
  "ranking_strategy_warning": null,
  "top_n": 20,
  "group_by": "user_scope",
  "scope_mode": "user_scope",
  "scope": {
    "manufacturer_count": 2,
    "manufacturer_codes": ["M1", "M2"]
  },
  "groups": [
    {
      "manufacturer_code": "user_scope",
      "available_count": 123,
      "returned_count": 20,
      "threshold_hit_count": 0,
      "overflow_count": 0,
      "shortage_count": 0,
      "entities": []
    }
  ],
  "warnings": []
}
```

当前正式 batch 的 `risk_entities` 有 `risk_probability_value`，但可能缺少 interval、frequency、business priority 的数值排序字段。因此只有显式请求 `ranking_strategy=mixed_v2` 且字段不足时，response 才会保留请求策略，同时将 `effective_ranking_strategy` / `ranking_strategy_effective` 降级为 `probability` 并返回 `missing_mixed_fields` warning。该降级不是重新解释概率，也不会产生自动派单。

接口不得返回 AUC、ECE、PR-AUC、XGBoost、feature ablation、leakage audit、hyperparameters 等内部算法指标。`observation_fill` 与 `one_shot_fill` 仅用于补足展示列表，返回项必须保留 `candidate_type`，且不标记为 high risk；one-shot 项不展示 recurring churn probability。

## Detector Result Table APIs

以下接口只读 Model 侧 result-batch detector 表，不在 `project` 后端重新计算 detector，不读取 raw/source DB，不依赖 `algo_main`。

- `GET /api/v1/daily-detector/status`：返回当前 detector result tables 是否 ready、最新 `run_date`、source 和 warnings。
- `GET /api/v1/daily-detector/dates`：返回可选日报日期，支持 `report_month`、`limit`。
- `GET /api/v1/daily-detector/clues`：兼容入口，返回每日规则线索。
- `GET /api/v1/detectors/catalog`：返回 detector catalog。`implemented` 表示可用；`interface_only`、`experimental`、`reserved` 不能包装成已上线能力。
- `GET /api/v1/detectors/runs`：返回 detector run 列表，支持 `report_month`、`run_date`、`limit`，包含 `detector_config_version`。
- `GET /api/v1/detectors/clues`：返回全部规则线索，支持 `detector_run_id`、`run_date`、`detector_id`、`detector_family`、`manufacturer_code`、`hospital_code`、`drug_group`、`only_monthly_high_risk`、`page`、`page_size`。
- `GET /api/v1/risk-entities/{risk_entity_id}/detector-evidence`：返回已有月度风险实体上的 detector evidence，支持 `detector_run_id`、`run_date`、`detector_family`、`detector_id`。
- `GET /api/v1/detectors/config-status`：返回当前结果使用的配置版本和配置修改语义。参数修改只在下一次 detector 巡检后生效，历史结果不会被静默改写。

语义约束：

- `detector_score` 是规则巡检分，不是概率，不代表 `risk_probability`。
- `daily_detector_clues` 可以包含非月报高风险对象，但这些对象不能因此成为 `risk_entities`。
- `high_risk_detector_evidence` 只附着到已有 `risk_entity_id`。
- 每日 detector 巡检结果可以每日变化，但月度模型概率来自低频、稳定、可复现的 monthly result batch。

## Display Lookup Readiness API

`GET /api/v1/display-lookup/status`

用于报告 `entity_display_lookup` 展示名映射表在当前后端链路中的 readiness。该接口只通过 `risk_model_core` repository/service 访问 `entity_display_lookup`，不直接扫描 result-batch 目录，不读取 raw/source 业务库，也不依赖 `algo_main`。

lookup 未就绪时返回 200：

```json
{
  "ready": false,
  "status": "missing",
  "source": "risk_model_core",
  "table": "entity_display_lookup",
  "row_count": 0,
  "warnings": ["ENTITY_DISPLAY_LOOKUP_NOT_AVAILABLE"]
}
```

lookup 就绪时返回 200：

```json
{
  "ready": true,
  "status": "ready",
  "source": "risk_model_core",
  "table": "entity_display_lookup",
  "row_count": 12345,
  "schema_version": "v1",
  "warnings": []
}
```

`/api/v1/workbench`、`/api/v1/risk-entities`、`/api/v1/proof-cases` 和 `/api/risk/my/top-entities` 可附带 `display_lookup_status`。lookup missing 不会导致这些 API 失败，也不会触发 raw DB 回源补展示名。

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

## Legacy Detector Runtime APIs

以下 `/api/v0/detectors` 接口是旧版后端运行型 detector / debug 链路，不是当前客户页面正式数据源。正式月报页面、每日规则线索页和详情页 evidence 面板应使用 `/api/v1/detectors/*`、`/api/v1/daily-detector/*` 和 `/api/v1/risk-entities/{risk_entity_id}/detector-evidence`。

### Detector 目录

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
