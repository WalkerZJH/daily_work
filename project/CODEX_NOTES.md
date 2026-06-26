# CODEX 维护说明

## 项目阶段

- 当前仍是算法验证阶段，目标是稳定跑通“真实数据库接入 -> canonical schema -> 特征快照 -> 主干模型候选 -> detector 证据 -> RiskCardCandidate/AlertPreview 草稿 -> 回测/调试”。
- 不做正式工单系统、正式派单流转、知识图谱、LLM 聊天式 Agent、自动调度、自动重训、复杂预警大屏或时间排期模块。
- `RiskCardCandidate` / `AlertPreview` / `Finding` 只是算法结果草稿，不是正式业务工单。
- 未经过回测与校准的分数不得解释为真实概率；`rule_score` 只能作为排序和调试参考。

## 命名与兼容

- 对外服务语义逐步收束为 `supply_chain_order_risk_algo_backend`。
- 代码或旧文档中仍出现 `terminal_guard_algo_backend` 时，视为 legacy name，不应继续扩散到新接口和新文档。

## 数据与安全

- 不得打印、复制、记录、提交或截图 `.env` 中的敏感信息。
- 数据库连接必须通过环境变量读取，不得硬编码账号、密码、host、库名或连接串。
- 当前本机可能使用 `DATABASE_URL`、`SQL_DATABASE_URL` 或拆分字段 `SQL_SERVER` / `SQL_USER` / `SQL_PASSWORD` / `SQL_DB` / `SQL_TABLE` / `SQL_PORT`。排查时只检查变量是否存在，不打印值。
- `SQLTableSourceAdapter` 必须只读访问真实库，不得 `SELECT *`，不得写入业务库。
- detector 不得直接依赖真实数据库中文列名，必须先映射到 canonical schema，再进入 feature snapshot 和 detector。
- 后续数据相关验证以真实数据库小窗口为准；CSV sample 仅保留为兼容测试路径，不作为新增算法验证主路径。

## 网络与端口

- 本机 GitHub 稳定方案是 SSH over 443 alias `github-work`，remote 应为 `github-work:WalkerZJH/daily_work.git`。
- 不要默认切回 HTTPS remote；之前 HTTPS/schannel 可能卡住或握手失败。
- 如果 GitHub 访问异常，优先运行仓库根目录 `.codex/check_github_work.ps1`。
- 后端默认端口是 8000；如果 8000 被 Windows 残留监听占用且无法正常释放，可临时使用 8001，并在前端 health 页面中把 backend base URL 设置为 `http://127.0.0.1:8001`。

## 中文乱码

- 项目文档、PowerShell 脚本和新增文本文件统一使用 UTF-8。
- PowerShell 脚本建议设置：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
```

- 如果真实业务数据出现 mojibake 或上传到外部模型后仍乱码，不要通过上传真实数据继续排查；优先在本机做小窗口 smoke test、字段存在性检查和数据质量统计。
- 真实数据乱码可能来自驱动编码、数据库列编码、本地数据保护/加密或导出链路，不能靠 detector 代码硬猜修复。

## P_alive / 主干预测口径

- 训练集构建可以使用多个历史 `origin_date`。
- smoke test、`/api/v0/backbone/predict` 和 health 页面主干预览只能表示单个 `as_of_date` 的当前预测。
- 对每个 `as_of_date`，每个 `org_code × product_line_code` 分析单元只输出 1 条 P_alive 候选结果。
- `analysis_unit_count` 来自有效订单去重，不应超过 `effective_order_rows`。
- `prediction_count` 应等于唯一 `analysis_unit_id` 数。
- `feature_column_count` 表示特征列数，不是预测次数，也不是单元格数量。
- `debug_features` 默认折叠；需要完整特征时显式传 `include_debug_features=true`。
- 模型缺失时 fallback 到 `interval_survival_proxy`，必须返回 warning，不得导致 dry-run、predict 或 smoke test 崩溃。

## Detector / Health 页面约束

- Detector category 固定为 `price_warning`、`delivery_response`、`terminal_change`、`sales_fluctuation`、`common_preprocess`。
- 需求 detector 使用 `*_warning` 对外口径；内部 detector 只能作为支撑、reserved 或 interface_only。
- Detector 阈值必须通过 `DetectorRuntimeConfig` / `/api/v0/detectors/config` 读取，不得在前端硬编码。
- `auto_baseline` 只用于测试和算法验证，不能冒充客户配置阈值。
- `ml_first` 和 `dl_first` 当前只预留接口；未实现时必须返回 warning 并 fallback。
- sales fluctuation 必须区分 `current_vs_previous_ratio` 和 `drop_rate`，不得把 `0/previous` 叙述成“变化比例为 0 因此异常”。
- Health 页面是日报式算法探查页，不是工单页、派单页或正式业务闭环。
- Health 页面企业、省份、产品线应通过 options API 下拉选择，避免用户手输 code。

## 文档同步

- 每次修改 API route、request schema 或 response schema，必须同步更新 `docs/API.md`。
- 每次修改 detector catalog 或阈值配置，必须同步更新 `docs/detector_catalog.md`。
- 每次修改主干模型训练、注册或 P_alive 实验口径，必须同步更新 `docs/model_training.md`、`docs/model_registry.md` 或 `docs/palive_experiment.md`。
