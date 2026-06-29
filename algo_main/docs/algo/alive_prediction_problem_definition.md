# 终端不丢 / 用户存活预测问题定义

## 目标

本任务的 v1 主线是基于 `entity × cutoff` 的全局概率模型，预测每个药企下医院和药品组合在未来窗口内停止采购的概率，并在概率输出之后计算潜在损失和业务优先级。

当前阶段只定义算法问题、数据口径、标签、指标和实验框架；不实现训练系统，不推进 detector，不读取真实数据库。

## 输入与主链路

稳定输入为：

```text
data/03_cleaned/bs_agent_dingdan_model_base.parquet
```

`model_base` 是清洗基础表，不是最终 `X_train`。后续必须先构建：

```text
model_base
-> fact_purchase_event
-> fact_entity_month
-> entity_cutoff_feature_table
-> labels
-> probability models
-> post-process ranking
```

不得直接把 `model_base` 全列喂给模型。

## v1 主线

v1 采用所有 `entity × cutoff` 样本共用一个全局概率模型。每个 entity 的差异由历史采购节奏、频次、数量/金额趋势、状态历史、静态实体属性和需求形态特征体现。

第一版不为每个医院药品组合单独训练模型。独立 entity 模型容易样本不足、不可回测、不易横向评估，也不利于药企内 TopK 输出。

## 预测对象

第一版业务任务定义为：

```text
在每个 cutoff 月，对每个 manufacturer_code × hospital_code × drug_group 单元，
预测其未来 H 窗口内停止采购的概率，
并基于流失概率、潜在损失和业务优先级生成 TopK 风险清单。
```

v1 推荐主粒度：

```text
primary_entity = manufacturer_code × hospital_code × drug_code
secondary_entity = manufacturer_code × hospital_code × drug_category_code
```

在配置和文档中统一使用 `drug_group` 表示可切换的药品分组字段。默认 `drug_group_source=drug_code`。

## 三个必须拆分的分数

主模型只预测概率：

```text
churn_probability_H = P(die_H = 1)
```

潜在损失是 as-of-cutoff 后处理估计：

```text
value_at_risk_amount_H = cutoff 前 12 个月平均月采购金额 × H
value_at_risk_quantity_H = cutoff 前 12 个月平均月采购数量 × H
```

`value_at_risk` 需保留 raw / nonnegative 双口径。raw 字段保留 as-of-cutoff 历史估计值，可能为负，用于质量诊断；nonnegative 字段使用 `max(raw, 0)`，用于业务排序。

业务优先级是排序分数，不是概率：

```text
business_priority_score_H = churn_probability_H × value_at_risk_amount_nonnegative_H_asof_cutoff
```

严禁把 `business_priority_score_H` 命名为 `risk_score` 或 `churn_probability`。严禁把 `die_H × value_at_risk_H` 作为主概率模型目标。

允许 cutoff 前可见的历史价值/规模特征进入 `churn_probability_H` 模型，例如最近 3/6/12 月采购金额和数量、历史月均金额和数量、entity 价值分层、`value_at_risk_amount_H_asof_cutoff`、`value_at_risk_quantity_H_asof_cutoff`。这些字段只能由 cutoff 前历史数据计算。禁止把 `business_priority_score_H`、未来真实损失、预测窗口真实采购金额/数量、或 `die_H × value_at_risk_H` 作为概率模型输入或目标。

## One-Shot 高价值沉默规则

当前主任务高度稀疏，大量 entity 只有一次采购。请把对象拆成三类：

```text
A. recurring / monitorable entity
   有一定历史采购行为，适合进入主概率模型或 rule baseline。

B. one-shot high-value silence entity
   只有一次采购，但该次采购价值较高，后续沉默。
   不强行交给概率模型预测，应进入业务规则关注池。

C. long-dead / low-value one-shot entity
   很久以前单次采购且价值低。
   不进入主模型，不进入重点业务关注池，只保留归档或低优先级观察。
```

one-shot 高价值沉默对象不是通过概率模型预测得到的，而是通过业务规则召回；它们不一定有可靠的 `churn_probability_H`，但有业务关注价值。不得把 `one_shot_business_priority_score` 解释为 `churn_probability_H`。

最终业务输出需要保留两类列表：

```text
model_probability_topk
one_shot_high_value_attention_list
```

## 标准输出字段

第一版输出至少包含：

```text
manufacturer_code
hospital_code
drug_group
cutoff_month

churn_probability_H3
churn_probability_H6
churn_probability_H12

value_at_risk_amount_H3
value_at_risk_amount_H6
value_at_risk_amount_H12

value_at_risk_quantity_H3
value_at_risk_quantity_H6
value_at_risk_quantity_H12

business_priority_score_H3
business_priority_score_H6
business_priority_score_H12

rank_by_probability_H3
rank_by_probability_H6
rank_by_probability_H12

rank_by_business_priority_H3
rank_by_business_priority_H6
rank_by_business_priority_H12
```

`rank_by_probability` 回答谁最可能流失；`rank_by_business_priority` 回答谁最值得优先处理。两套排名都必须保留。

## 候选路线定位

v1 主线：

```text
Logistic Regression baseline
LightGBM small
CatBoost small
XGBoost stable comparison
```

二阶段或备选路线：

```text
BG/NBD
Pareto/NBD
Weibull / Cox / AFT
purchase interval baseline
ranking / rerank models
```

生存模型、BG-NBD、Pareto-NBD 可作为二阶段解释、baseline 或特征来源，不作为 v1 唯一主干。

## 禁止事项

- 不修改已冻结的 BS_Agent_DingDan v2 清洗语义。
- 不读取真实数据库。
- 不提交 parquet/csv/xlsx/joblib/pkl/skops/zip 运行产物。
- 不把金额字段解释为真实货币金额。
- 不用金额/数量推断真实单价。
- 不把 `purchase_time` 原样转时间戳作为普通数值特征。
- 不随机切分 `entity × cutoff` 作为主验证。
