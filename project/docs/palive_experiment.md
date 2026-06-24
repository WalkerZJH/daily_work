# P_alive 实验

当前阶段是基于真实数据库数据做算法验证。输出用于候选算法对比和回测，不是正式概率、正式工单或最终预警决策。

## 分析单元

分析单元为“医疗机构 × 产品线”：

- `org_code`
- `product_line_code`
- `analysis_unit_id = org_code|product_line|product_line_code`

输入只来自 canonical orders。数据库原始中文列名必须先完成 canonical 映射，P_alive 实验服务不得直接依赖原始列名。

## 候选算法

### palive_lgbm

用途：作为当前优先训练的机器学习主干候选，用于预测“医疗机构 × 产品线”在未来 H 天内是否停购。

训练输出的是 `label_churn_H` 的分类模型。后端推理时会将停购风险转换为候选 `p_alive`，但在完成校准前仍不能解释为正式概率。

### interval_survival_proxy

用途：为平稳采购或波动采购提供可解释的基线代理。

计算口径：

- `d = as_of_date - last_purchase_date`
- `I = 历史相邻采购间隔`
- `p_unit = P(I >= d | 当前分析单元历史间隔)`
- `p_cohort = P(I >= d | 同产品线 / 医院等级 / 省份 / 需求形态 cohort)`
- `p_alive_proxy = w * p_unit + (1 - w) * p_cohort`
- `w = n_intervals / (n_intervals + k)`

默认 `k = 5`。冷启动单元必须使用 cohort prior 或返回低置信度，不允许在样本不足时强行给高置信结果。

### bgnbd_candidate

用途：为 BG/NBD 类主干模型保留候选接口。

当前服务不会把 BG/NBD 定为唯一方向。若依赖缺失、历史样本不足、拟合未启用或拟合失败，该候选返回 `null` 并附带已脱敏的警告信息，不得伪造分数。

在完成回测和校准前，任何 BG/NBD 输出都不能解释为真实流失概率或真实存活概率。

### intermittent_overdue_proxy

用途：避免对间断型、块状型采购过度惩罚。

v1 实现采用 Croston/SBA 思路的间隔 fallback：

- 有当前单元历史时，估计期望补货间隔。
- 当前单元历史不足时，使用 cohort prior。
- 超过期望间隔后缓慢衰减，而不是简单用趋势下降或采购间隔拉长判定流失。

当需求形态为 `intermittent` 或 `lumpy` 时，优先选择该候选，而不是普通趋势下降规则。

## 输出字段

每个结果包含：

- `analysis_unit_id`
- `org_code`、`org_name`
- `product_line_code`、`product_line_name`
- `as_of_date`
- `demand_profile`
- `days_since_last_purchase`
- `purchase_interval_stats`
- `p_alive_proxy_interval`
- `p_alive_bgnbd`
- `p_alive_intermit_proxy`
- `selected_p_alive`
- `selected_model_name`
- `model_confidence`
- `warnings`
- `debug_features`
- `data_sufficiency`（在后端主干推理输出中体现）

`selected_p_alive` 是用于实验排序和回测对比的候选模型分数。只有经过真实数据回测、校准和业务验收后，才可能作为正式概率使用。
