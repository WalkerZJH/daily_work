# API

当前对外服务名称收束为 `supply_chain_order_risk_algo_backend`，API 前缀为 `/api/v0`。代码中如仍出现 `terminal_guard_algo_backend`，仅作为 legacy name 兼容。当前阶段是算法链路验证阶段：所有 P_alive、主干风险分、RiskCardCandidate 都是实验候选输出，不是正式工单，也不是已校准概率。

## 巡检 dry-run

`POST /api/v0/inspection/dry-run`

请求体：

```json
{
  "source_type": "database",
  "dataset_name": "database:BS_Agent_DingDan",
  "csv_path": null,
  "as_of_date": "2026-06-24",
  "date_from": "2026-06-10",
  "date_to": "2026-06-24",
  "user_id": "admin",
  "enterprise_code": null,
  "province": null,
  "province_code": null,
  "row_limit": 5000
}
```

`source_type` 仍默认兼容 `"csv"`，但后续真实数据验证以 `"database"` 为主。数据库模式通过 `SQLTableSourceAdapter` 从环境变量 `DATABASE_URL` 读取 `BS_Agent_DingDan`，不会硬编码账号、密码、host 或库名。

响应重点字段：

- `risk_card_candidates`：算法结果草稿，供后续线索管理分析使用，不是正式业务工单。
- `top_risk_clues`：兼容旧前端和旧测试的字段。
- `warning_summary`：数据质量、模型 fallback、detector warning 汇总。
- `backbone`：主干模型/代理模型输出状态。

`rule_score` 和 `risk_score_deprecated` 只是未校准排序信号，不得解释为概率。

## 真实数据库 smoke test

`POST /api/v0/smoke-test/database`

用于真实库小窗口链路验证：读取小段订单数据，运行数据质量检查、FeatureSnapshot、BackbonePrediction 和 dry-run，并返回少量 P_alive 候选预览。

请求体：

```json
{
  "as_of_date": "2026-06-24",
  "days": 14,
  "row_limit": 5000,
  "enterprise_code": null,
  "province": null,
  "province_code": null,
  "include_debug_features": true
}
```

约束：

- 默认读取 `as_of_date` 向前 14 天，`row_limit` 最大 5000。
- 只投影 canonical schema 需要的列，不执行 `SELECT *`。
- active 模型不可用时 fallback 到 `palive_interval_proxy`，接口不应整体失败。
- `palive_preview` 最多返回 10 条，避免暴露大量真实明细。
- 所有真实数据输出必须保留 `warnings` 和 `debug_features`。

响应示例：

```json
{
  "summary": {
    "source_type": "database",
    "table": "BS_Agent_DingDan",
    "as_of_date": "2026-06-24",
    "date_from": "2026-06-10",
    "date_to": "2026-06-24",
    "row_limit": 5000,
    "loaded_rows": 0,
    "valid_order_rows": 0,
    "unit_count": 0,
    "feature_count": 0,
    "prediction_count": 0,
    "risk_card_count": 0,
    "palive_preview": [],
    "warning_summary": {},
    "elapsed_seconds": 0.0
  },
  "palive_preview": [],
  "warning_summary": {}
}
```

如果未配置 `DATABASE_URL`，接口返回 400 和清晰错误信息，不暴露连接串或异常堆栈。

## 数据新鲜度 smoke test

`POST /api/v0/smoke-test/freshness`

用于轻量检查当前数据库窗口是否有数据，暂不实现持久化 last_check、自动调度、自动重训。

请求体：

```json
{
  "as_of_date": "2026-06-24",
  "days": 14,
  "date_from": null,
  "date_to": null,
  "row_limit": 5000,
  "enterprise_code": null,
  "province": null,
  "province_code": null
}
```

响应：

```json
{
  "source_type": "database",
  "max_order_time": "2026-06-24T00:00:00",
  "row_count": 1234,
  "date_from": "2026-06-10",
  "date_to": "2026-06-24",
  "is_changed_since_last_check": null,
  "note": "v0 only reports freshness; no scheduler is implemented",
  "warning_summary": {}
}
```

## Detector 目录

`GET /api/v0/detectors/catalog`

返回所有 detector 元数据，包括 `detector_id`、`name_zh`、`category`、`status`、`required_fields`、`optional_fields`、`required_features`、`required_columns`、`implemented`、`enabled_by_default` 和 `notes`。

对外展示优先使用初始需求 detector，例如：

- `low_price_warning`
- `price_spread_warning`
- `delivery_rejection_warning`
- `delivery_delay_warning`
- `low_delivery_rate_warning`
- `terminal_lost_warning`
- `new_terminal_warning`
- `purchase_quantity_fluctuation_warning`
- `purchase_frequency_fluctuation_warning`

内部 detector 如 `substitution_risk`、`cycle_deviation`、`sku_shrink` 当前标注为 `reserved` 或 `interface_only`，不作为本阶段正式需求功能扩展。

`POST /api/v0/detectors/run`

用于 health 页面主动发起 detector 推理，只证明算法链路可运行，不生成正式工单。

```json
{
  "source_type": "sample",
  "dataset_name": "sample",
  "as_of_date": "2026-06-24",
  "days": 14,
  "row_limit": 5000,
  "category": null,
  "enabled_detectors": ["low_delivery_rate_warning"],
  "enterprise_code": null,
  "province_code": null
}
```

返回：

```json
{
  "summary": {
    "loaded_rows": 0,
    "valid_rows": 0,
    "detector_count": 0,
    "implemented_detector_count": 0,
    "interface_only_detector_count": 0,
    "result_count": 0,
    "returned_result_count": 0,
    "hit_count": 0,
    "warning_count": 0,
    "elapsed_seconds": 0.0
  },
  "detector_results": [],
  "warning_summary": {},
  "debug": {}
}
```

`detector_results` 默认最多返回前 50 条；summary 中保留总结果数。缺字段时返回 `MISSING_REQUIRED_FIELDS`，不会静默跳过或崩溃。

## 用户配置

`GET /api/v0/users/me/config`

读取请求头 `X-User-Id`；开发和本地环境未提供时默认 `admin`。返回用户权限、用户偏好和合并后的有效 detector 配置。

`PATCH /api/v0/users/{user_id}/preferences`

只更新用户偏好，不更新权限：

```json
{
  "enabled_detectors": ["ip_interval", "inactive_terminal"]
}
```

`admin` 可以修改任意用户。普通用户只能修改自己。若试图启用超出 category 权限的 detector，接口返回 `403`。

`GET /api/v0/config/effective?user_id=js_manager_001`

返回经过 permission 过滤后的有效 detector 配置。

## P_alive 实验

`GET /api/v0/backbone/palive/config`

返回 P_alive 实验参数，例如 `interval_prior_k`、冷启动阈值、BG/NBD 最小历史订单数等。

`PATCH /api/v0/backbone/palive/config`

只修改本地实验配置，用于算法验证；不写入生产业务数据库。

`POST /api/v0/backbone/palive/experiment`

基于 canonical orders，按“医疗机构 × 产品线”分析单元运行多个 P_alive 候选算法：

```json
{
  "source_type": "database",
  "dataset_name": "database:BS_Agent_DingDan",
  "as_of_date": "2026-06-24",
  "date_from": "2026-06-10",
  "date_to": "2026-06-24",
  "row_limit": 5000,
  "enabled_models": [
    "interval_survival_proxy",
    "bgnbd_candidate",
    "intermittent_overdue_proxy"
  ]
}
```

输出是带 `warnings` 和 `debug_features` 的实验候选结果，用于回测对比和算法选择，不是正式工单，也不是已校准概率。

## 训练数据构建

`POST /api/v0/training/build-dataset`

开发阶段用于从数据库 source 构建主干模型训练集。CSV 仍保留兼容测试，但真实算法验证以数据库数据为准。

```json
{
  "source_type": "database",
  "dataset_name": "database:BS_Agent_DingDan",
  "train_start": "2026-01-01",
  "train_end": "2026-06-24",
  "horizon_days": 90,
  "freq": "M",
  "output_path": "artifacts/training/palive_training_dataset.csv",
  "enterprise_code": null,
  "province": null,
  "province_code": null,
  "row_limit": 5000
}
```

返回样本数、正负样本数、正样本比例、时间范围、输出路径和数据质量 warning。

## Backbone 推理

`POST /api/v0/backbone/predict`

基于当前 active backbone 模型输出“医疗机构 × 产品线”的 `BackbonePrediction`：

```json
{
  "source_type": "database",
  "dataset_name": "database:BS_Agent_DingDan",
  "as_of_date": "2026-06-24",
  "date_from": "2026-06-10",
  "date_to": "2026-06-24",
  "row_limit": 5000,
  "enterprise_code": null,
  "province": null,
  "province_code": null
}
```

如果 `configs/model_registry.yaml` 指向的 active 模型不可用，后端会自动 fallback 到 `palive_interval_proxy`，并在 `warnings` 中返回原因，不会让接口整体失败。输出中的 `p_alive` 当前是候选模型结果，未经过真实回测和概率校准。
# 当前 detector / health / backbone API 口径

当前 health 页面是“日报式算法探查页”，不是工单页。所有 detector 运行接口都必须携带明确时间口径：

- `as_of_date`：本次探查日期。
- `lookback_days`：风险发现窗口，默认 30 天。
- `baseline_days`：历史基线窗口，默认 180 天。
- `history_start_date`：可选，只使用该日期之后的历史订单。

Detector 配置接口：

- `GET /api/v0/detectors/config`
- `GET /api/v0/detectors/{detector_id}/config`
- `PATCH /api/v0/detectors/{detector_id}/config`

`DetectorRuntimeConfig` 字段包括 `detector_id`、`category`、`enabled`、`mode`、`params`、`scope_type`、`scope_value`、`updated_by`、`updated_at`。当前只实现 `rule` 和 `auto_baseline`；`ml_first`、`dl_first` 只预留接口，未实现时返回 `ML_MODEL_NOT_IMPLEMENTED` 或 `DL_MODEL_NOT_IMPLEMENTED` warning，并 fallback 到 rule/auto_baseline。

Detector 运行接口：

- `POST /api/v0/detectors/{detector_id}/run`
- `POST /api/v0/detectors/run-by-category`
- `POST /api/v0/detectors/run`

每条 `detector_results` 返回 `as_of_date`、`lookback_start_date`、`baseline_start_date`、`baseline_end_date`、`run_scope`、`statistics`、`evidence_items`、`sample_order_ids`、`related_entities`、`warnings`、`narrative`。

Options 接口：

- `GET /api/v0/options/enterprises`
- `GET /api/v0/options/provinces`
- `GET /api/v0/options/product-lines?enterprise_code=...&province_code=...`
- `GET /api/v0/options/detector-categories`
- `GET /api/v0/options/detectors?category=...`

前端 health 页面必须通过 options API 填充企业、省份、产品线、category 和 detector 下拉框，用户不应手输 `enterprise_code` 或 `province_code`。

`POST /api/v0/backbone/predict` 支持 `history_start_date` 和 `product_line_code`。输出表示在 `as_of_date` 这个检测日，每个 `org_code × product_line_code` 分析单元的 alive 候选状态。模型缺失时 fallback 到 `interval_survival_proxy`，并在 warnings 中说明。当前 `p_alive` 仍是算法候选输出，不能解释为真实概率。
