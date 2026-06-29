# Alive / Die 标签定义

## 采购事件定义

第一版采购事件：

```text
purchase_event = purchase_time 非空 且 order_detail_id 有效
```

只要发生采购事件，就认为该 entity 在对应窗口内仍然活跃。

第一版不要因为以下状态否定采购事件：

```text
拒绝配送
无法配送
配送失败
未到货
退货
```

这些状态只能作为历史特征、履约解释或二阶段分析依据，不作为 v1 alive/die 标签的决定条件。

## Entity 与 cutoff

标签粒度：

```text
manufacturer_code × hospital_code × drug_group × cutoff_month
```

`drug_group` 默认来自 `drug_code`，可通过 feature view 配置切换到 `drug_category_code` 做对照实验。

## 多窗口标签

第一版必须同时支持：

```text
H = 3 个月
H = 6 个月
H = 12 个月
```

`cutoff_month` 表示月末快照，`purchase_month` 表示 `purchase_time` 所在月份。标签窗口边界：

```text
feature months <= cutoff_month
label months in [cutoff_month + 1, cutoff_month + H]
```

对每个 H：

```text
alive_H = cutoff 后 H 窗口内存在 purchase_event
die_H = 1 - alive_H
```

输出：

```text
label_alive_H3
label_die_H3
label_alive_H6
label_die_H6
label_alive_H12
label_die_H12
```

## 标签可观测性

训练样本必须保证标签窗口已经闭合。对 H=12，若数据最大月份为 2025-12，则最大可训练 cutoff 不能晚于 2024-12。

验证切分必须按 H 做 purged split：

```text
max_train_cutoff + H <= valid_start
```

## 禁止泄露字段

以下字段不得进入特征：

```text
next_purchase_time
next_purchase_month
days_until_next_purchase
label_alive_H*
label_die_H*
churn_probability_H*
business_priority_score_H*
rank_by_probability_H*
rank_by_business_priority_H*
```

多窗口标签之间也不得互相污染。训练 H3 模型时不得使用 H6/H12 标签或未来窗口统计作为特征。

## 标签分布报告

第一轮 sanity check 至少输出：

```text
row_count by cutoff_month
entity_count by cutoff_month
positive_rate label_die_H3/H6/H12
alive_rate label_alive_H3/H6/H12
label_available_cutoff_min/max by H
positive_rate by manufacturer_code
positive_rate by demand_pattern_type
```

若标签极端失衡，需要先报告问题，再决定是否调整候选集或窗口，不直接进入复杂模型调参。
