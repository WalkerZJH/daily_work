# CODEX 维护说明

- 每次修改 API，都必须同步更新 `docs/API.md`。
- 不得打印、复制、记录或提交 `.env` 中的敏感信息。
- Detector 必须消费 canonical schema 字段，不得直接依赖数据库原始中文列名。
- 当前范围不实现正式工单系统，只输出 `RiskCardCandidate` / `AlertPreview` 等算法结果草稿。
- 未校准分数不得解释为概率。`rule_score` 只用于排序和调试。
- 用户配置必须区分 permission 和 preference。preference 不能越过 permission。
- 当前阶段是基于真实数据库数据做算法验证，不做时间排期，也不做完整产品闭环。
- 保留未来开发接口，但优先建设算法链路调通、算法候选验证、数据质量诊断和回测对比能力。
- 所有算法输出均为实验候选，必须保留 `debug_features` 和 `warnings`。
- `RiskCardCandidate` / `AlertPreview` 是结果草稿，不是正式业务工单。
- 当前新增主干模型能力必须围绕“训练数据构建 -> 模型训练 -> 模型注册 -> 后端推理调用”闭环。
- 模型产物和训练数据属于本地生成内容，不提交真实文件；只保留 README 和配置样例。
- `palive_lgbm`、interval proxy、BG/NBD candidate 都是候选主干，未回测校准前不得解释为正式概率。
- 后续数据相关工作以真实数据库数据为准；CSV sample 仅保留为兼容测试路径，不作为新增算法验证主路径。
- 当前真实库接入只做小窗口 smoke test 和人工触发验证；不得默认全量读取、全量训练、自动调度、自动重训或自动切换 active model。
- 对外服务语义逐步收束为 `supply_chain_order_risk_algo_backend`；代码内如仍出现 `terminal_guard_algo_backend`，视为 legacy name，除非专门做兼容迁移，不应继续扩展旧命名。
- Health 页面 detector 推理只用于验证链路是否可运行；需求 detector 使用 `*_warning` 对外口径，内部 detector 只能作为支撑、reserved 或 interface_only，不得扩展成正式产品功能。
