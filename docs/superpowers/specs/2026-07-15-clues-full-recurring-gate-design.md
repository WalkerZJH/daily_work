# Clues 纯规则语义与 Full Recurring 批次门禁设计

## 目标

本轮只完成两项收口：

1. `clues.html` 只表达 Daily Detector 命中事实，并始终进入 rule-only clue detail。
2. 将 Full Recurring 月度主干批次修复为可验证、可发现、可供后续 `P1-02` 消费的正式批次。

本轮不实现 `P1-02` 页面、分页 API 或任何新的 Detector 规则；不重训模型，也不重跑 Detector。

## 语义边界

- Recurring 候选概率、H3/H6/H12、金额和排名属于月度主干结果。
- Detector clue、Detector score、命中说明和 evidence payload 属于独立的日度规则证据层。
- Detector score 不是风险概率；rule-only clue 不创建 risk entity。
- Detector 批次不可用不能阻断 Full Recurring 主干批次发布；两者分别被 API 发现和读取。

## 当前根因

`full-recurring-v1` 的前三张表已写出，但在写入 `risk_card_evidence.parquet` 时失败。证据值列同时包含空字符串和数值，PyArrow 无法为 `object` 列推导稳定类型，抛出 `ArrowTypeError`。现有逐表原子写入只能保护单个 Parquet，不能保护整批结果，因此失败后留下了没有 manifest 的半成品目录。

## 设计

### 1. Clues 的纯规则视图

Clues 查询服务只返回 `hit_flag=true` 的记录。页面删除月度候选关联筛选和月度字段，仅保留生产企业、观察日期、Detector family、Detector subtype、规则分数、严重程度、命中原因和证据摘要等规则事实。任何 Clues 行都以 `detector_clue_id` 构造 `clue-detail.html?clueId=...`，不根据 `risk_entity_id` 分流。

### 2. 稳定证据序列化

风险卡证据的空指标值使用缺失值而非空字符串；Parquet 写入器也对混合 object 标量列进行显式稳定化：数值和空白值保持数值/空值，无法统一为数值的混合值以可读字符串稳定持久化。该规则不将 Detector score 映射为概率，也不改变候选概率或排序。

### 3. 主干批次 staging 与发布

月度主干结果先写入同级 staging 目录。只有所有主干结果表、manifest 和 `validate_result_batch` 均成功后，才原子发布为版本化 batch 目录。失败时 staging 目录保留为诊断产物，但不会拥有正式 batch 路径或 manifest。

为支持 Detector 独立，主干 manifest 明确声明其提供月度候选结果；核心 validator 仅要求主干表。Detector 表仍按已有独立契约验证，但不是主干发布前置条件。

### 4. 批次与 API 发现

从冻结 artifact 和现有正式输入物化新的、未使用的 Full Recurring batch ID。主干候选 API 只从具有有效 manifest 且声明月度候选数据的 batch 中选择对应月份的最新正式批次。Detector 服务只从含完整 Detector 表的 batch 选择证据来源，因此继续使用现有正式 Detector 批次。

## 验证

- 单元测试复现并修复混合空字符串/数值的 Parquet 写入失败。
- 批次组装测试证明失败不会发布 manifest 或正式目录；成功批次通过 validator 且双计数等于实际 Recurring 行数。
- Clues 服务/前端契约测试证明只返回命中项、没有月度筛选或字段，详情 URL 始终携带 `clueId`。
- 在新正式 batch 上验证 Repository/API 发现、生产企业过滤、H3/H6/H12、概率、金额和排序字段可读。
- 更新路线图：`P1-01=DONE`，且仅在全部门禁通过后标记 `P1-02=READY`。
