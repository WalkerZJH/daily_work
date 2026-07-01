## 1. 模块定位

M6 是 detector evidence cache / evidence timeline 模块。

**当前阶段仅保留接口，暂不实现。**

M6 的设计目的是为未来解决以下问题：

```text
同一高风险 entity 可能连续多个 cutoff 进入候选池；
detector 证据可能持续、加重、缓解或新增；
线索卡需要展示风险是否连续存在，而不是只看单点结果。
```

本阶段只定义 cache 的角色、字段和未来接入位置，不实现 cache 写入、读取、复用或增量更新逻辑。

---

## 2. 为什么暂不实现

M6 暂不实现，原因：

```text
1. 当前 M1–M4 尚未工程落地；
2. detector 输出尚未稳定；
3. cache 需要稳定 evidence schema；
4. 过早实现会增加复杂度；
5. 当前阶段先生成单 cutoff evidence 即可。
```

因此本阶段只要求后续模块在字段设计中预留：

```text
evidence_id
evidence_hash
previous_evidence_id
evidence_timeline_reference
```

---

## 3. 未来输入

未来 M6 的输入来自 M4：

```text
detector_evidence_results
```

字段：

```text
candidate_id
entity_key
cutoff_month
detector_family
detector_name
hit_flag
severity
confidence
evidence_window_start
evidence_window_end
evidence_fields
evidence_values
reason_code
```

---

## 4. 未来 cache key

建议 cache key：

```text
manufacturer_code
hospital_code
drug_group
drug_group_source
detector_family
detector_name
evidence_window_type
cutoff_month
```

其中：

```text
evidence_window_type:
  last_1m
  last_3m
  last_6m
  last_12m
  asof_cutoff
```

---

## 5. 未来 cache 字段

未来 cache 表建议字段：

```text
evidence_id
previous_evidence_id
manufacturer_code
hospital_code
drug_group
drug_group_source
cutoff_month

detector_family
detector_name
hit_flag
severity
confidence
reason_code

evidence_hash
evidence_payload
evidence_window_start
evidence_window_end

persistence_count
first_seen_cutoff
last_seen_cutoff
trend_status
new_evidence_added
data_quality_status
created_at
```

---

## 6. trend_status 定义

未来枚举：

```text
new
persistent
worsening
improving
resolved
unknown
```

含义：

```text
new:
  第一次出现该类证据

persistent:
  连续多个 cutoff 出现，严重度变化不大

worsening:
  证据持续且 severity 增强

improving:
  证据仍存在但 severity 下降

resolved:
  上期存在，本期不再命中

unknown:
  数据缺失或无法比较
```

---

## 7. 未来输出

未来 M6 输出：

```text
evidence_timeline_summary
```

字段：

```text
candidate_id
entity_key
detector_name
current_hit_flag
previous_hit_flag
persistence_count
trend_status
timeline_summary
evidence_timeline_reference
```

---

## 8. 与 M7 的接口

M7 structured evidence bundle 需要预留字段：

```text
evidence_timeline_available
evidence_timeline_reference
evidence_persistence_summary
```

当前阶段这些字段可置为：

```text
evidence_timeline_available = false
evidence_timeline_reference = null
evidence_persistence_summary = "not_implemented_in_v1"
```

---

## 9. 当前阶段要求

本阶段：

```text
1. 不实现 cache 读写；
2. 不生成 cache 文件；
3. 不复用历史 detector 结果；
4. 不做 evidence timeline；
5. 只在 schema 中预留字段。
```

---

```

---

