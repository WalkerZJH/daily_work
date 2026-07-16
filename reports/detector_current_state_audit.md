# Detector 当前实现自检与 Release A 状态

## 输入与边界

- 正式输入只来自 `cleaned-detector-facts-v2-20260716` cleaned Parquet；拒绝 ClickHouse/raw manifest。
- 清洗层已保留标准化 `purchase_unit`，Detector 不增加 raw 血缘依赖。
- 未运行月度特征工程、月度预测、候选池或 scorer。
- 月度输出不创建 Detector 表；二者只通过精确 observation registry 关联。

## 当前能力

- 已实现 10 个非配送 Detector，均可按 `--detector-id` 独立发布。
- 14 家企业 × 10 个 Detector = 140 条只读运行快照，数值唯一来自管理员参数表。
- 本次观察日：2026-01-01；运行组件：10；结果：450,740；命中：26,389。
- config missing：0。
- registry 精确登记 `2026-01-01`，关联上一完整月 `2025-12`；当前状态：`ready`。

## 严重问题与门禁结论

- 工程门：通过。
- 配置策略：当前阶段只读管理员参数；无审批流程、无用户修改入口，账号 × 企业个性化参数支线暂不实现。
- 清洗数据截至 `2026-06-24`；本次观察日使用完整 2025 历史，并已在真实数据中覆盖低价、首购和恢复采购命中。
- 曾发现长路径发布后无法被 Python/registry 重开；已增加发布前路径长度门禁，并以短路径重试成功验证。原长路径诊断目录保留。
