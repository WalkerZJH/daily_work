# Detector 当前实现自检与 Release A 状态

## 输入与边界

- 正式输入只来自 `cleaned-detector-facts-v2-20260716` cleaned Parquet；拒绝 ClickHouse/raw manifest。
- 清洗层已保留标准化 `purchase_unit`，Detector 不增加 raw 血缘依赖。
- 未运行月度特征工程、月度预测、候选池或 scorer。
- 月度输出不创建 Detector 表；二者只通过精确 observation registry 关联。

## 当前能力

- 已实现 10 个非配送 Detector，均可按 `--detector-id` 独立发布。
- 14 家企业 × 10 个 Detector = 140 条显式配置，无全局静默 fallback。
- 本次观察日：2026-07-16；运行组件：10；结果：479,820；命中：38,593。
- config missing：0。
- registry 精确登记 Detector 日期；对应月度概率不存在时明确显示 unavailable。

## 严重问题与门禁结论

- 工程门：通过。
- 业务门：待定。当前企业参数为 `copied_template_unapproved`，必须完成业务验收。
- 当前数据截至日早于观察日，因此当日型低价/首购/恢复采购规则没有命中，不得视为规则失效。
- 曾发现长路径发布后无法被 Python/registry 重开；已增加发布前路径长度门禁，并以短路径重试成功验证。原长路径诊断目录保留。
