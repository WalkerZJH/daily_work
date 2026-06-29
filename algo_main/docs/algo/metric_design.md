# 终端不丢 / 用户存活指标设计

## 指标分层

指标必须拆成两组：

```text
A. 概率模型 metrics：评价 churn_probability_H 是否可靠
B. 业务排序 metrics：评价 business_priority_score_H 是否有业务价值
```

概率模型评估必须使用：

```text
churn_probability_H
```

业务排序评估使用：

```text
business_priority_score_H
```

不得用 `business_priority_score_H` 替代概率质量指标。

业务排序默认使用非负潜在损失：

```text
business_priority_score_H
= churn_probability_H × value_at_risk_amount_nonnegative_H_asof_cutoff
```

`value_at_risk_amount_raw_H*_asof_cutoff` 只用于数据质量报告和特征消融，不直接用于 business priority 默认排序。

## One-Shot 业务规则指标

`one_shot_high_value_attention_list` 独立于 `model_probability_topk`。one-shot 高价值沉默对象通过业务规则召回，不要求模型输出可校准流失概率。相关报告只评价召回规模、价值分布和业务关注列表覆盖，不纳入主概率模型 calibration 指标。

## 概率模型指标

每个窗口 H=3/6/12 单独计算：

```text
BrierScore_H
LogLoss_H
CalibrationCurve_H
ECE_H
AUC_H
PR_AUC_H
Precision@K_H by churn_probability
Recall@K_H by churn_probability
NDCG@K_H by churn_probability
Lift@K_H by churn_probability
```

用途：

```text
回答模型是否能可靠预测谁最可能流失。
```

## 业务排序指标

每个窗口 H=3/6/12 单独计算：

```text
CapturedValue@K_H
ValueWeightedNDCG@K_H
ExpectedLossCaptured@K_H
TopK total value_at_risk_H
TopK average business_priority_score_H
Precision@K_H by business_priority as guardrail
```

用途：

```text
回答加入潜在损失后，业务优先级排序是否能捕获更多高价值风险对象。
```

## K 取值

固定 K：

```text
10
20
50
100
```

比例 K：

```text
top_1_pct
top_5_pct
top_10_pct
```

不同药企 entity 数量不同，固定 K 和比例 K 都需要保留。

## 分组维度

指标必须先按 cutoff 计算，再做时间聚合。支持以下分组：

```text
cutoff_month
manufacturer_code
drug_group
drug_category_code
hospital_level_code
demand_pattern_type
```

药企 TopK 输出和评估必须按 `manufacturer_code` 分组，避免跨药企混排。

## 排名字段

输出必须同时保留：

```text
rank_by_probability_H3/H6/H12
rank_by_business_priority_H3/H6/H12
```

两套排名分别回答：

```text
rank_by_probability = 谁最可能流失
rank_by_business_priority = 谁最值得优先处理
```

## 报告文件建议

第一轮实验建议输出报告，而不是模型产物：

```text
reports/alive_prediction/label_distribution_report.md
reports/alive_prediction/feature_null_report.md
reports/alive_prediction/baseline_metric_report.md
reports/alive_prediction/model_metric_report.md
reports/alive_prediction/calibration_report.md
reports/alive_prediction/topk_sample_review.md
```

报告中必须标明金额字段为脱敏相对金额，不能解释为真实货币金额。
