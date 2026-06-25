# CODEX 维护说明

- 每次修改 API，必须同步更新 `docs/API.md`。
- 不得打印、复制、记录或提交 `.env` 中的敏感信息。
- 数据库连接必须通过环境变量读取，不得硬编码账号、密码、host 或库名。
- Detector 必须消费 canonical schema 字段，不得直接依赖数据库原始中文列名。
- 对外服务语义逐步收束为 `supply_chain_order_risk_algo_backend`；代码内如仍出现 `terminal_guard_algo_backend`，视为 legacy name。
- 当前阶段是算法验证阶段，不做时间排期、正式工单系统、知识图谱、LLM 聊天式 Agent、复杂预警大屏或完整产品闭环。
- `RiskCardCandidate` / `AlertPreview` / `Finding` 是算法结果草稿，不是正式业务工单。
- 所有算法输出必须保留 `warnings`、`data_quality_summary` 或必要的 `debug_features`，用于验证算法合理性。
- 未经回测和校准的分数不得解释为真实概率；`rule_score` 只可用于排序参考和调试。
- 用户配置必须区分 permission 和 preference；preference 不得越过 permission。
- 后续数据相关工作以真实数据库数据为准；CSV sample 仅保留为兼容测试路径，不作为新增算法验证主路径。
- 真实库接入只做小窗口 smoke test 和人工触发验证；不得默认全量读取、全量训练、自动调度、自动重训或自动切换 active model。

## P_alive / 主干预测口径

- 训练集构建可以使用多个历史 `origin_date`。
- smoke test、`/api/v0/backbone/predict` 和 health 页面主干预览只能表示单个 `as_of_date` 的当前预测。
- 对每个 `as_of_date`，每个 `org_code × product_line_code` 分析单元只输出 1 条 P_alive 候选结果。
- `analysis_unit_count` 来自有效订单去重，不应超过 `effective_order_rows`。
- `prediction_count` 必须等于唯一 `analysis_unit_id` 数。
- `feature_column_count` 表示特征列数，不是预测次数，也不是单元格数量。
- `debug_features` 默认折叠；需要完整特征时显式传 `include_debug_features=true`。
- 模型缺失时 fallback 到 `interval_survival_proxy`，必须返回 warning，不得导致 dry-run 或 smoke test 崩溃。

## Detector / Health 页面约束

- Detector category 固定为 `price_warning`、`delivery_response`、`terminal_change`、`sales_fluctuation`、`common_preprocess`。
- 需求 detector 使用 `*_warning` 对外口径；内部 detector 只能作为支撑、reserved 或 interface_only。
- Detector 阈值必须通过 `DetectorRuntimeConfig` / `/api/v0/detectors/config` 读取，不得在前端硬编码。
- `auto_baseline` 只用于测试和算法验证，不能冒充客户配置阈值。
- `ml_first` 和 `dl_first` 当前只预留接口；未实现时必须返回 warning 并 fallback。
- sales_fluctuation 必须区分 `current_vs_previous_ratio` 和 `drop_rate`，不得把 `0/previous` 叙述成“变化比例为 0 因此异常”。
- Health 页面是日报式算法探查页，不是工单页、派单页或正式业务闭环。
- Health 页面企业、省份、产品线必须通过 options API 下拉选择，不让用户手输 code。
