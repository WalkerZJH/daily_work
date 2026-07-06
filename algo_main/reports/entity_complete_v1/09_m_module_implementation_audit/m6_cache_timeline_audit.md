# M6 Detector Evidence Cache / Evidence Timeline 审计

## 状态

`interface_only` / `intentionally_deferred`。

## 设计状态

M6 设计文档明确当前阶段只保留接口，不实现：

- cache 读写
- cache 文件
- 历史 detector 结果复用
- evidence timeline
- persistence/trend 计算

## 代码和产物状态

旧链路 detector/evidence bundle 中有一些保留字段：

- `evidence_id`
- `evidence_hash`
- `previous_evidence_id`
- `evidence_timeline_reference`
- `evidence_timeline_available`
- `evidence_persistence_summary`

但这些字段当前没有真实 cache/timeline 语义：

- `previous_evidence_id` 多为空
- `evidence_timeline_reference` 多为空
- `evidence_timeline_available=false`
- `evidence_persistence_summary=not_implemented_in_v1`

`entity_complete_v1` 当前也没有 M6 cache/timeline artifact。

## 结论

M6 不能算实现；当前状态符合设计中的 interface-only/deferred。近期不建议优先开发 M6，除非 M4 row-level detector 已稳定且业务确认需要跨 cutoff 展示风险延续。

