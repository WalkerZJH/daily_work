# API

当前服务名仍为 `terminal_guard_algo_backend`，API 前缀为 `/api/v0`。

## 巡检 dry-run

`POST /api/v0/inspection/dry-run`

请求体在原 CSV 结构基础上扩展：

```json
{
  "source_type": "csv",
  "dataset_name": "sample",
  "csv_path": null,
  "as_of_date": "2026-06-24",
  "user_id": "admin",
  "enterprise_code": null,
  "province": null,
  "province_code": null,
  "row_limit": null
}
```

为兼容现有样例和测试，`source_type` 默认是 `"csv"`。当设置为 `"database"` 时，后端通过 `SQLTableSourceAdapter` 从环境变量 `DATABASE_URL` 读取数据库。数据库 dry-run 会按有效用户配置自动叠加省份权限过滤；如果请求已显式提供更窄的省份过滤，则使用请求值。

响应包含：

- `risk_card_candidates`：确定性规则生成的 `RiskCardCandidate` 草稿列表，供后续线索管理智能体消费。
- `top_risk_clues`：兼容旧前端和测试的字段，当前包含同一批候选结果。
- `detector_hit_distribution`、`warning_summary`、`backbone`：用于调试命中、数据质量与主干模型状态。

`rule_score` 和 `risk_score_deprecated` 只是未校准的排序信号，不是概率，也不能解释为“流失概率”或“存活概率”。

## Detector 目录

`GET /api/v0/detectors/catalog`

返回所有 detector 元数据，包括 `detector_id`、`category`、`family`、`version`、`required_features`、`required_columns`、`implemented`、`enabled_by_default`。

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

`admin` 可以修改任意用户。普通用户只能修改自己的偏好。如果试图启用超出 category 权限的 detector，接口返回 `403`。

`GET /api/v0/config/effective?user_id=js_manager_001`

返回经过 permission 过滤后的有效 detector 配置。

## P_alive 实验

`GET /api/v0/backbone/palive/config`

返回 P_alive 实验参数，例如 `interval_prior_k`、冷启动阈值、BG/NBD 最小历史订单数等。

`PATCH /api/v0/backbone/palive/config`

只修改本地实验配置，用于算法验证；不会写入生产业务数据库。

`POST /api/v0/backbone/palive/experiment`

基于 canonical orders，按“医疗机构 × 产品线”分析单元运行多个 P_alive 候选算法：

```json
{
  "source_type": "csv",
  "dataset_name": "sample",
  "as_of_date": "2025-12-31",
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

开发阶段用于从 CSV 或数据库 source 构建主干模型训练集：

```json
{
  "source_type": "csv",
  "dataset_name": "sample",
  "train_start": "2025-01-01",
  "train_end": "2025-12-31",
  "horizon_days": 90,
  "freq": "M",
  "output_path": "artifacts/training/palive_training_dataset.csv"
}
```

返回样本数、正负样本数、正样本比例、时间范围、输出路径和数据质量警告。

## Backbone 推理

`POST /api/v0/backbone/predict`

基于当前 active backbone 模型输出“医疗机构 × 产品线”的 `BackbonePrediction`：

```json
{
  "source_type": "csv",
  "dataset_name": "sample",
  "as_of_date": "2025-12-31"
}
```

如果 `configs/model_registry.yaml` 指向的 active 模型不可用，后端会自动回退到 `palive_interval_proxy`，并在 `warnings` 中返回原因，不会让接口整体失败。
