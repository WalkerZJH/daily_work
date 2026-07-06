# M7 Structured Evidence Bundle 审计

## 状态

新链路为 `partially_implemented`；旧链路为 `implemented_legacy_only`。

## 当前 entity_complete_v1 证据

当前新链路生成：

- `algo_main/data/entity_complete_v1/08_evidence/m7_evidence_bundle_sample.csv`
- 500 行 sample
- 包含 `allowed_claims`
- 包含 `forbidden_claims`
- 包含 `bundle_complete`
- 明确 forbidden：LLM card、auto dispatch、detector/interval/business priority as probability

该产物是样例原材料，不是完整 `structured_evidence_bundle`。

## legacy 证据

旧链路 `alive_prediction_evidence_bundle_v1` 生成过完整 structured evidence bundle：

- total rows：3,246
- candidate_type 覆盖 recurring_business_priority / one_shot_attention / demand_shape_observation
- allowed_claims coverage：1.0000
- forbidden_claims coverage：1.0000
- recommended_action_candidates coverage：1.0000
- auto_dispatch_allowed all false
- evidence_timeline_available all false
- LLM not called
- final line cards not generated

## 缺口

新链路缺少：

- 完整 candidate_type 三类 bundle
- M5 row-level status decision 输入
- row-level detector_evidence_list
- timeline interface fields 标准输出
- recommended_action_candidates
- model_limitations_note
- data_quality_note
- final line-card material completeness audit

## 结论

M7 当前不能等同于正式线索卡。下一步应先补齐 M5/M4 当前链路明细，再生成 full structured evidence bundle；LLM line card 仍应延后。

