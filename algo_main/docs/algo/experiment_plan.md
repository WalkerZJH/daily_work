# 终端不丢 / 用户存活实验计划

## 当前阶段边界

本计划用于指导后续 facts/features/labels/metrics 代码实现。当前优先交付文档与配置，不直接训练模型，不输出模型文件，不读取真实数据库。

## 第一轮：数据与标签 sanity check

目标：确认任务是否可学。

实验设置：

```text
input = data/03_cleaned/bs_agent_dingdan_model_base.parquet
entity = manufacturer_code × hospital_code × drug_code
time_grain = monthly
H = 3/6/12
```

产物：

```text
fact_purchase_event
fact_entity_month
entity_demand_profile
entity_cutoff_feature_table
label distribution report
feature null report
```

检查项：

```text
label_die_H3/H6/H12 正负样本比例
每个 cutoff 的 entity 数量
每个 manufacturer_code 的样本量
冷启动样本比例
字段 null rate / distinct count
泄露字段是否被排除
```

通过标准：

1. 标签不是极端失衡到不可学。
2. 每个验证 cutoff 有足够 entity。
3. H3/H6/H12 指标差异可解释。
4. feature view 没有引入标签、未来字段或 raw/name/label 文本字段。

## 第二轮：baseline 与小模型

模型：

```text
规则 baseline
Logistic Regression
LightGBM small
CatBoost small
XGBoost stable comparison
```

基础特征组：

```text
recency
frequency
quantity / amount trends
interval
entity age
static category
```

输出：

```text
baseline_metric_report
model_metric_report
calibration_report
TopK sample review
```

注意：

`churn_probability_H` 是概率输出。`business_priority_score_H` 仅作为后处理排序分数。

## 第三轮：算法框架对比

比较对象：

```text
probability scorer: Logistic Regression / LightGBM / CatBoost / XGBoost
rule baseline: interval overdue / recent drop
second-stage survival: BG/NBD / Pareto-NBD / purchase interval baseline
rerank: LightGBM Ranker / XGBoost Ranker / CatBoost Ranking
```

排序或二阶段模型不得替代 v1 概率主线。若排序模型输出未经校准，不得解释为流失概率。

## 第四轮：特征组消融

按组增量加入：

```text
A. recency/frequency 基础特征
B. + 数量/金额趋势
C. + 采购间隔特征
D. + 状态历史特征
E. + 需求形态特征
F. + 高基数类别特征
G. + value_at_risk 特征
```

每组输出：

```text
Precision@K_H
NDCG@K_H
Lift@K_H
BrierScore_H
ECE_H
CapturedValue@K_H
```

消融的目标是回答哪些信号真正有效，哪些特征组只提升业务价值排序但不提升概率质量，哪些特征组造成不稳定。

## 验证方案

主验证：

```text
rolling-origin temporal split
```

示例：

```text
Fold 1:
train cutoff <= 2022-12
valid cutoff = 2023-01 ~ 2023-03

Fold 2:
train cutoff <= 2023-03
valid cutoff = 2023-04 ~ 2023-06

Fold 3:
train cutoff <= 2023-06
valid cutoff = 2023-07 ~ 2023-09
```

对 H=3/6/12 分别满足：

```text
max_train_cutoff + H <= valid_start
```

## 交付检查

第一轮代码实现前必须确认：

- feature view 已定义 input table、entity grain、target、allowed/excluded columns 和 leakage rules。
- metrics config 已区分 probability metrics 与 business ranking metrics。
- value_at_risk 不参与主概率目标。
- 不提交真实数据、CSV、Parquet 或模型文件。
