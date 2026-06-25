# P_alive 候选算法实验说明

当前目标不是把某一个模型定为唯一主干，而是在真实订单数据上比较多个 P_alive 候选算法的解释性、稳定性和回测表现。所有输出都属于算法验证候选，未经过真实回测和概率校准前，不能解释为正式概率。

## 分析单元

分析单元固定为：

```text
org_code × product_line_code
```

即“医疗机构 × 产品线”。`analysis_unit_id` 由这两个字段组成。

## 训练与推理的口径区别

训练集构建可以使用多个历史 `origin_date` 生成滚动样本，用于训练、回测和模型比较。

smoke test、`/api/v0/backbone/predict` 和 health 页面的主干算法预览不同：它们只表示单个检测日 `as_of_date` 的当前状态。对每个 `as_of_date`，每个 `org_code × product_line_code` 只输出 1 条 P_alive 候选结果。

## 输出统计口径

- `raw_order_rows`：本次请求同一数据切口下进入 canonical 后、过滤有效采购前的订单行数。
- `effective_order_rows`：有效采购订单行数。
- `analysis_unit_count`：有效订单去重后的 `org_code × product_line_code` 数。
- `prediction_count`：P_alive 候选预测条数，正常情况下等于 `analysis_unit_count`。
- `feature_column_count`：特征快照的列数，不是预测次数，也不是单元格数量。

`analysis_unit_count` 不应超过 `effective_order_rows`。如果口径不一致，后端返回 `BACKBONE_UNIT_COUNT_INCONSISTENT` warning。

## 候选算法

### interval_survival_proxy

基于历史采购间隔和同侪 cohort 的可解释代理模型。

- `d = as_of_date - 最近一次采购时间`
- `I = 历史相邻采购间隔`
- `p_unit = P(I >= d | 当前 unit 历史间隔)`
- `p_cohort = P(I >= d | 同产品线/医院等级/省份/需求形态 cohort)`
- `p_alive_proxy = w * p_unit + (1 - w) * p_cohort`
- `w = n_intervals / (n_intervals + k)`

样本不足时必须降低 confidence，不得伪造高置信输出。

### bgnbd_candidate

BG/NBD 只作为候选模型。依赖缺失、拟合失败或样本不足时返回 warning，不影响整体 dry-run。

### lgbm_churn_candidate

训练目标是预测未来 `horizon_days` 内是否停购，输出 `p_churn_candidate` 后转换为 `p_alive = 1 - p_churn_candidate`。未校准前必须标注 experimental / not production-calibrated probability。

## debug_features

列表接口默认折叠 `debug_features`，只保留关键字段，例如：

- `days_since_last_purchase`
- `purchase_count_90d`
- `purchase_count_365d`
- `median_interval_days`
- `demand_profile`

需要完整特征时，调用方必须显式传入 `include_debug_features=true`。
