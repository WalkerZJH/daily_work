# Detector 跨日重复命中聚合设计

## 1. 边界

聚合层是 Daily Detector 事实服务的只读派生层，不属于月度预测链路。它只读取已经原子发布的 `daily_detector_results.parquet`，不读取 ClickHouse 原始字段，不调用月度特征工程、scorer 或候选筛选，也不改写任何日级 Detector component。聚合实体键直接使用 result 表的 `drug_code`；不得从为未来生产线/药品分组预留的 `drug_group` 反推 `drug_code`。当前阶段二者相等只是数据现状，不是长期血缘规则。

数据来源必须是同一 `observation_date × detector_id` 下当前选中的最新不可变 component。失败、staging 或未发布目录不参与聚合。

## 2. 粒度与计数语义

实体键固定为：

```text
manufacturer_code × hospital_code × drug_code
```

事件键固定为：

```text
entity_key × observation_date × detector_id
```

同一事件键即使源文件重复，也只计一次。仅 `hit_flag=true` 的正式 clue 进入事件层。

聚合表每一行表示“某实体在某观察日期至少命中一个 Detector”，因此当前企业和日期下同一实体仅一行：

- `current_detector_count`：该实体当日命中的不同 Detector 数；
- `current_detector_ids`：当日命中的 Detector ID 集合；
- `cumulative_hit_count`：从聚合起始日期到该日，唯一 `date × detector_id` 事件的累计数；
- `cumulative_hit_day_count`：从聚合起始日期到该日，至少命中过一次的累计自然日数；
- `historical_detector_ids`：截至该日曾命中过的 Detector ID 集合；
- `first_hit_date` / `last_hit_date`：截至该日的首次/最近命中日期。

“历史上命中过某 Detector”采用 `historical_detector_ids` 精确集合匹配，不使用字符串包含匹配。历史窗口包含当前观察日期，不读取未来日期。

## 3. 物化和发布

物化入口为 `python -m production_pipeline.materialize_detector_event_aggregates`，输入为正式 Detector batch root、起止日期和新 `run_id`。输出为独立不可变目录：

```text
detector_event_aggregates/
  batch_id=<end_date>-<run_id>/
    detector_event_aggregates.parquet
    detector_event_aggregation_validation.json
    manifest.json
```

先写入根目录下独立 `.detector_event_aggregation_staging`，校验通过后再原子 rename。已发布目录禁止覆盖；重跑必须使用新 `run_id`。源日级 Parquet 不移动、不删除、不合并覆盖。

## 4. 算法与规模约束

读取过程按日期选择 component，每个 Detector 从 result 表仅投影事件所需列并过滤 `hit_flag=true`。首先全局去重事件键，然后使用 groupby、排序和累计运算生成当前计数与跨日累计值。

历史 Detector 集合按 Detector 种类的固定小维度计算首次命中日期；禁止在逐实体循环中反复执行 DataFrame 全表布尔过滤。设计核对时，当前新格式 component 中有 20 个正式 result 文件，约 16 MiB；其余旧 component 只有 clue，不能作为本聚合层的 `drug_code` 血缘来源。完成 365 天 × 10 Detector 新格式回填后，聚合读取量随 3,650 个 component 线性增长。C 盘核对时可用空间约 104.9 GiB。

## 5. API

聚合查询接口按 `observation_date` 和 `manufacturer_code` 定位实体行，支持：

- `hospital_code`、`drug_code` 精确筛选；
- `historical_detector_id` 精确历史集合筛选；
- `current_detector_count` 或 `cumulative_hit_count` 排序；
- 分页。

接口返回当前与历史 Detector ID 数组、两个累计计数和首次/最近命中日期。展示筛选只影响本次请求，不持久化偏好，也不触发 Detector 重跑或聚合重跑。

## 6. 验收不变量

1. 输出键 `observation_date × manufacturer_code × hospital_code × drug_code` 唯一。
2. `current_detector_count == len(current_detector_ids)`。
3. `cumulative_hit_count`、`cumulative_hit_day_count` 对同一实体随日期单调不减。
4. `current_detector_ids` 是 `historical_detector_ids` 的子集。
5. 历史筛选只返回精确命中过目标 Detector 的实体。
6. 多 Detector 同日命中仍只产生一条实体聚合行。
7. 聚合发布前后所有源 component manifest 和 Parquet 保持不变。
8. 聚合产物仅为 Parquet、JSON manifest 和验证报告，不增加数据库或运行时依赖。
