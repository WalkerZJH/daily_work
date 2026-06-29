# Entity 粒度设计与研究备忘

## 推荐主粒度

第一版主分析单元：

```text
manufacturer_code × hospital_code × drug_code
```

对应统一字段：

```text
manufacturer_code
hospital_code
drug_group
drug_group_source = drug_code
```

原因：

1. 系统最终服务药企，`manufacturer_code` 必须贯穿全流程。
2. 当前没有真实 `product_line_code`，不能把 `drug_category_code` 假设为产品线。
3. `drug_code` 粒度足够细，后续可上卷到产品线或药品类别。
4. 输出时可以自然按 `manufacturer_code` 做药企内 TopK。

## 备选粒度

第一版保留一个次级粒度用于稳定性对比：

```text
manufacturer_code × hospital_code × drug_category_code
```

其他候选粒度只作为后续研究，不在第一轮主流程中并行展开：

```text
hospital_code × drug_code
hospital_code × drug_category_code
hospital_code × product_line_code
manufacturer_code × hospital_code × product_line_code
```

## drug_group 口径

`drug_group` 是算法层抽象字段，不是原始字段。它由配置控制：

```yaml
drug_group:
  default_source: drug_code
  alternatives:
    - drug_category_code
```

当 `drug_group_source=drug_code` 时，`drug_group = drug_code`。当 `drug_group_source=drug_category_code` 时，`drug_group = drug_category_code`。

不得在当前阶段使用未来统计、未来产品线映射或模型结果构造 `drug_group`。

## 候选集规则

每个 cutoff 保留两种候选集口径。默认使用 monitorable。

```text
all_seen candidate =
  截至 cutoff 曾经出现过采购事件的 entity

monitorable candidate =
  截至 cutoff 曾经出现过采购事件，
  且距离上次采购不超过 max_monitor_gap
```

禁止把 cutoff 后才首次出现的 entity 加入历史 cutoff 的候选集。

初始配置：

```yaml
candidate_policy:
  default: monitorable
  max_monitor_gap_months: 12
  alternatives:
    - all_seen
```

## 冷启动处理

第一版冷启动定义：

```text
cold_start_flag = 历史采购事件数不足阈值，或历史活跃月份不足阈值
```

冷启动样本只能使用 cutoff 前可见信息和 group prior，例如同药品、同医院等级、同药企历史统计。不得用全量历史均值回填早期 cutoff。

## 分组评估

粒度稳定性需要至少按以下维度分层观察：

```text
manufacturer_code
drug_group
drug_category_code
hospital_level_code
demand_pattern_type
active_month_count_asof_cutoff
cold_start_flag
```

先按 cutoff 月计算指标，再做时间聚合，避免跨时间混排。
