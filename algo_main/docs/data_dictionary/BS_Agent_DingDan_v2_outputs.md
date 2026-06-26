# BS_Agent_DingDan v2 输出字段字典

本文档是 BS_Agent_DingDan v2 清洗 pipeline 的统一字段字典，适用于以下输出：

- `data/03_cleaned/bs_agent_dingdan_model_base.parquet`
- `exports/clean/bs_agent_dingdan_clean_sample_v2.csv`
- `exports/clean/bs_agent_dingdan_audit_sample.csv`
- `exports/eda/field_quality_gate_v2.csv`
- `exports/eda/numeric_desensitization_report_v2.csv`
- `exports/eda/numeric_negative_samples_v2.csv`
- `exports/eda/order_status_mapping_coverage.csv`
- `exports/eda/order_status_suspicious_mapping.csv`
- `exports/mappings/order_status_lifecycle_map.csv`
- `exports/eda/bs_agent_dingdan_quality_report_v2.md`

## 总体口径

`model_base` 不是最终 X_train。model_base 不是最终 X_train，它是后续 facts/features/train_sets 的稳定基础表。不同任务应通过 feature view 明确 allowed columns、excluded columns、target、cutoff、leakage rules 后，再生成各自的小 X。

`row_uid/order_detail_id 是追溯键，不直接进入 X`。`purchase_time 是时间索引`，用于排序、切分、聚合和 cutoff 控制，不应原样作为普通连续数值特征进入 X。`region_dirty_flag 是质量控制字段`，可保留在 model_base 用于过滤、分层评估和质量报告，正式训练默认不进入 X。状态语义字段可能造成标签泄漏，尤其当目标涉及完成、失败、终止、到货、配送质量时，必须通过 feature view 控制。

`delivery_rate/arrival_rate/overall_arrival_rate 是数量比例，不是配送时长`。所有数量和金额字段仍处在脱敏口径下，只允许做相对关系、比例、趋势和质量检查。禁止用金额/数量推断真实单价，也禁止用采购价校验采购金额/采购数量。

## 表级说明

| 表或文件 | 用途 | 是否算法主链路输入 | 说明 |
| --- | --- | --- | --- |
| `model_base` | 下游 facts/features 的清洗基础表 | 是 | 只保留追溯键、时间键、代码字段、质量 flag、状态编码、脱敏数值和比例字段。 |
| `clean_v2` | 人工观察和汇报复核 | 否 | 可以保留 raw/name/label/code/比例字段，不作为训练矩阵。 |
| `audit` | 追溯、排错、质量核验 | 否 | 保留清洗前后对照、状态映射原因、地区冲突、药品编码冲突等审计信息。 |
| `field_quality_gate_v2.csv` | 字段质量和默认 X 角色检查 | 否 | 由 clean_v2 统计 null、distinct、是否进入 model/audit 和推荐角色。 |
| `numeric_desensitization_report_v2.csv` | 数值脱敏与比例质量报告 | 否 | 统计 zero/negative rate、ratio 分布、状态与数量矛盾。 |
| `numeric_negative_samples_v2.csv` | 负数样本追溯 | 否 | 仅列出出现负数的数值字段样本。 |
| `order_status_mapping_coverage.csv` | 状态映射覆盖率 | 否 | 统计状态映射总量、已映射、未映射、覆盖率。 |
| `order_status_suspicious_mapping.csv` | 状态映射人工复核项 | 否 | 输出命中人工复核规则或映射失败的状态。 |
| `order_status_lifecycle_map.csv` | 状态生命周期映射表 | 否 | 状态词到生命周期编码的可复核映射。 |
| `bs_agent_dingdan_quality_report_v2.md` | Markdown 汇总报告 | 否 | 汇总行列数、主键、地区、药品编码、状态映射、数值质量和输出路径。 |

## model_base 字段

| field_name | 所在表 | 中文含义 | 字段来源 | 生成规则 | 取值范围或枚举 | 是否可进入 model_base | 是否默认进入 X_train | 是否为追溯键 | 是否为质量控制字段 | 是否存在标签泄漏风险 | 是否仅用于 audit/review | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| row_uid | model_base, clean_v2, audit | 行级唯一追溯键 | 原始字段 | 由数据唯一标识符标准化得到 | 字符串 | 是 | 否 | 是 | 否 | 低 | 否 | 只用于追溯、join 和排错。 |
| order_detail_id | model_base, clean_v2, audit | 订单明细 ID | 原始字段 | 由订单明细ID标准化得到 | 字符串 | 是 | 否 | 是 | 否 | 低 | 否 | 不直接进入 X。 |
| purchase_time | model_base, clean_v2 | 采购时间 | 原始字段 | 由采购时间解析为时间字段 | 日期/时间 | 是 | 否 | 否 | 否 | 中 | 否 | 时间索引、排序、切分、聚合依据。 |
| province_code | model_base, clean_v2, audit | 省级行政区划代码 | 派生字段 | `county_code` 前 2 位 + `0000` | 6 位地区码 | 是 | 视任务配置 | 否 | 否 | 低 | 否 | 以 county_code 派生结果为准。 |
| city_code | model_base, clean_v2, audit | 市级行政区划代码 | 派生字段 | `county_code` 前 4 位 + `00` | 6 位地区码 | 是 | 视任务配置 | 否 | 否 | 低 | 否 | 不直接复用 raw_city_code。 |
| county_code | model_base, clean_v2, audit | 县区行政区划代码 | 原始字段 | 由县区编码标准化得到 | 6 位地区码或缺失 | 是 | 视任务配置 | 否 | 否 | 低 | 否 | 当前唯一可信地区字段。 |
| region_dirty_flag | model_base, clean_v2, audit | 地区编码冲突标记 | 派生字段 | 用原始 `raw_city_code` 与由 `county_code` 派生的 `city_code` 比较 | `1`=冲突，`0`=未发现冲突 | 是 | 否 | 否 | 是 | 低 | 否 | 可用于过滤、分层评估和质量报告。 |
| hospital_code | model_base, clean_v2 | 医疗机构编码 | 原始字段 | 标准化医疗机构编码 | 字符串 | 是 | 视任务配置 | 否 | 否 | 低 | 否 | 医院名称不进入 model_base。 |
| drug_code | model_base, clean_v2, audit | 药品编码 | 原始字段 | 标准化药品编码 | 字符串 | 是 | 视任务配置 | 否 | 否 | 低 | 否 | 不与 insurance_drug_code 合并。 |
| drug_category_code | model_base, clean_v2, audit | 药品类别编码 | 映射字段 | 由样本中的药品类别枚举映射为整数编码 | 正整数或缺失 | 是 | 视任务配置 | 否 | 否 | 低 | 否 | 不是 product_line_code。 |
| distributor_code | model_base, clean_v2, audit | 配送企业编码 | 原始字段 | 标准化配送企业编码 | 字符串 | 是 | 视任务配置 | 否 | 否 | 低 | 否 | 配送企业名称不进入 model_base。 |
| manufacturer_code | model_base, clean_v2, audit | 生产企业编码 | 原始字段 | 标准化生产企业编码 | 字符串 | 是 | 视任务配置 | 否 | 否 | 低 | 否 | 生产企业名称不进入 model_base。 |
| hospital_level_code | model_base, clean_v2, audit | 医疗机构等级编码 | 映射字段 | 由医疗机构等级映射得到 | 配置映射整数或缺失 | 是 | 视任务配置 | 否 | 否 | 低 | 否 | 详细等级只进 audit。 |
| ownership_type_code | model_base, clean_v2, audit | 所有制形式编码 | 映射字段 | 由所有制形式映射得到 | 配置映射整数或缺失 | 是 | 视任务配置 | 否 | 否 | 低 | 否 | 原始文本不进入 model_base。 |
| order_phase_code | model_base, clean_v2, audit | 订单生命周期阶段编码 | 映射字段 | 由 `order_status_raw` 通过 lifecycle map 映射 | 见“订单状态字段枚举” | 是 | 视任务和泄漏规则 | 否 | 否 | 高 | 否 | 状态语义字段，预测完成/失败/终止/到货等目标时可能泄漏。 |
| delivery_state_code | model_base, clean_v2, audit | 配送状态编码 | 映射字段 | 由 `order_status_raw` 通过 lifecycle map 映射 | 见“订单状态字段枚举” | 是 | 视任务和泄漏规则 | 否 | 否 | 高 | 否 | 预测配送质量或到货状态时需谨慎。 |
| order_terminal_flag | model_base, clean_v2, audit | 订单是否终态 | 映射字段 | 由状态映射表给出 | `1`=终态，`0`=非终态，`-1`=不确定 | 是 | 视任务和泄漏规则 | 否 | 否 | 高 | 否 | 终态类目标中可能直接泄漏。 |
| order_failure_flag | model_base, clean_v2, audit | 订单是否失败/取消/拒绝类状态 | 映射字段 | 由状态映射表给出 | `1`=失败语义，`0`=正常推进，`-1`=不确定 | 是 | 视任务和泄漏规则 | 否 | 否 | 高 | 否 | 失败类目标中可能直接泄漏。 |
| return_quantity | model_base, clean_v2 | 退回数量 | 原始字段 | 数值化后缺失填 0 | 脱敏数量，可为 0 或正负值 | 是 | 视任务配置 | 否 | 可作为质量检查 | 中 | 否 | 不代表真实绝对数量。 |
| raw_sensitive_purchase_quantity | model_base, clean_v2 | 采购数量（脱敏） | 原始字段 | 数值化保留 | 脱敏数量 | 是 | 视任务配置 | 否 | 可作为质量检查 | 中 | 否 | 可做比例和趋势，不还原真实数量。 |
| raw_sensitive_purchase_amount | model_base, clean_v2 | 采购金额（脱敏） | 原始字段 | 数值化保留 | 脱敏金额 | 是 | 视任务配置 | 否 | 可作为质量检查 | 中 | 否 | 禁止与数量相除推真实单价。 |
| raw_sensitive_delivery_quantity | model_base, clean_v2 | 配送数量（脱敏） | 原始字段 | 数值化保留 | 脱敏数量 | 是 | 视任务配置 | 否 | 可作为质量检查 | 中 | 否 | 可用于配送比例。 |
| raw_sensitive_delivery_amount | model_base, clean_v2 | 配送金额（脱敏） | 原始字段 | 数值化保留 | 脱敏金额 | 是 | 视任务配置 | 否 | 可作为质量检查 | 中 | 否 | 可用于金额比例。 |
| raw_sensitive_arrival_quantity | model_base, clean_v2 | 到货数量（脱敏） | 原始字段 | 数值化保留 | 脱敏数量 | 是 | 视任务配置 | 否 | 可作为质量检查 | 中 | 否 | 到货目标中需按 cutoff 聚合避免泄漏。 |
| raw_sensitive_arrival_amount | model_base, clean_v2 | 到货金额（脱敏） | 原始字段 | 数值化保留 | 脱敏金额 | 是 | 视任务配置 | 否 | 可作为质量检查 | 中 | 否 | 到货目标中需按 cutoff 聚合避免泄漏。 |
| delivery_rate | model_base, clean_v2, audit | 配送数量占采购数量比例 | 派生字段 | `raw_sensitive_delivery_quantity / raw_sensitive_purchase_quantity` | 非空数值或缺失 | 是 | 视任务配置 | 否 | 可作为质量检查 | 中 | 否 | 数量比例，不是时间差。 |
| arrival_rate | model_base, clean_v2, audit | 到货数量占配送数量比例 | 派生字段 | `raw_sensitive_arrival_quantity / raw_sensitive_delivery_quantity` | 非空数值或缺失 | 是 | 视任务配置 | 否 | 可作为质量检查 | 中 | 否 | 数量比例，不是配送时长。 |
| overall_arrival_rate | model_base, clean_v2, audit | 到货数量占采购数量比例 | 派生字段 | `raw_sensitive_arrival_quantity / raw_sensitive_purchase_quantity` | 非空数值或缺失 | 是 | 视任务配置 | 否 | 可作为质量检查 | 中 | 否 | 数量比例，不是配送时长。 |
| delivery_amount_to_purchase_amount_ratio | model_base, clean_v2 | 配送金额占采购金额比例 | 派生字段 | `raw_sensitive_delivery_amount / raw_sensitive_purchase_amount` | 非空数值或缺失 | 是 | 视任务配置 | 否 | 可作为质量检查 | 中 | 否 | 金额比例，不能用于单价还原。 |
| arrival_amount_to_delivery_amount_ratio | model_base, clean_v2 | 到货金额占配送金额比例 | 派生字段 | `raw_sensitive_arrival_amount / raw_sensitive_delivery_amount` | 非空数值或缺失 | 是 | 视任务配置 | 否 | 可作为质量检查 | 中 | 否 | 金额比例，不能用于单价还原。 |
| arrival_amount_to_purchase_amount_ratio | model_base, clean_v2 | 到货金额占采购金额比例 | 派生字段 | `raw_sensitive_arrival_amount / raw_sensitive_purchase_amount` | 非空数值或缺失 | 是 | 视任务配置 | 否 | 可作为质量检查 | 中 | 否 | 金额比例，不能用于单价还原。 |

## clean_v2 额外字段

| field_name | 所在表 | 中文含义 | 字段来源 | 生成规则 | 取值范围或枚举 | 是否可进入 model_base | 是否默认进入 X_train | 是否为追溯键 | 是否为质量控制字段 | 是否存在标签泄漏风险 | 是否仅用于 audit/review | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| raw_province_code | clean_v2, audit | 原始省编码 | 原始字段 | 由省编码标准化保留 | 字符串或缺失 | 否 | 否 | 否 | 是 | 低 | 是 | 用于与派生省市码对照。 |
| raw_city_code | clean_v2, audit | 原始市编码 | 原始字段 | 由市编码标准化保留 | 字符串或缺失 | 否 | 否 | 否 | 是 | 低 | 是 | region_dirty_flag 使用它与派生 city_code 比较。 |
| order_status_raw | clean_v2, audit | 原始订单状态 | 原始字段 | 标准化保留原始状态文本 | 文本 | 否 | 否 | 否 | 是 | 高 | 是 | 用于映射复核，不进入 model_base。 |
| order_status_norm | clean_v2, audit | 归一化订单状态 | 派生字段 | 对原始状态做空白和格式归一 | 文本 | 否 | 否 | 否 | 是 | 高 | 是 | 映射表匹配键。 |
| order_phase_label | clean_v2, audit | 生命周期阶段标签 | 映射字段 | 由状态映射表给出 | 见状态映射表 | 否 | 否 | 否 | 否 | 高 | 是 | label 字段不进入 model_base。 |
| delivery_state_label | clean_v2, audit | 配送状态标签 | 映射字段 | 由状态映射表给出 | 见状态映射表 | 否 | 否 | 否 | 否 | 高 | 是 | label 字段不进入 model_base。 |
| needs_manual_review | clean_v2, audit | 是否需要人工复核 | 映射字段 | 状态未知、未映射或命中人工复核规则时为 True | `True`/`False` | 否 | 否 | 否 | 是 | 中 | 是 | True 表示状态或映射结果需要人工复核；False 表示暂不需要人工复核。 |
| mapping_failure_reason | clean_v2, audit | 映射失败或复核原因 | 派生字段 | `order_phase_code=0` 时为 `unknown_or_unmapped_status`；需要复核时为 `manual_review_status`；否则为空字符串 | `unknown_or_unmapped_status`、`manual_review_status`、空字符串 | 否 | 否 | 否 | 是 | 中 | 是 | 用于 review/audit。 |
| hospital_name | clean_v2 | 医疗机构名称 | 原始字段 | 原始文本标准化保留 | 文本 | 否 | 否 | 否 | 否 | 低 | 是 | 人工观察字段。 |
| distributor_name | clean_v2, audit | 配送企业名称 | 原始字段 | 原始文本标准化保留 | 文本 | 否 | 否 | 否 | 否 | 低 | 是 | 不进入 model_base。 |
| manufacturer_name | clean_v2, audit | 生产企业名称 | 原始字段 | 原始文本标准化保留 | 文本 | 否 | 否 | 否 | 否 | 低 | 是 | 不进入 model_base。 |
| product_name | clean_v2, audit | 商品名 | 原始字段 | 原始文本标准化保留 | 文本 | 否 | 否 | 否 | 否 | 低 | 是 | 不进入 model_base。 |
| hospital_level_raw | clean_v2, audit | 医疗机构等级原始值 | 原始字段 | 原始等级文本保留 | 文本 | 否 | 否 | 否 | 是 | 低 | 是 | 主字段用于等级映射。 |
| hospital_level_label | clean_v2, audit | 医疗机构等级标签 | 映射字段 | 由等级映射表给出 | 文本或缺失 | 否 | 否 | 否 | 否 | 低 | 是 | label 字段不进入 model_base。 |
| ownership_type_raw | clean_v2, audit | 所有制形式原始值 | 原始字段 | 原始文本保留 | 文本或缺失 | 否 | 否 | 否 | 是 | 低 | 是 | 映射为 ownership_type_code。 |
| drug_category_raw | clean_v2, audit | 药品类别原始值 | 原始字段 | 原始文本保留 | 文本或缺失 | 否 | 否 | 否 | 是 | 低 | 是 | 映射为 drug_category_code。 |
| raw_sensitive_purchase_price | clean_v2 | 采购价（脱敏） | 原始字段 | 数值化保留 | 脱敏金额 | 否 | 否 | 否 | 是 | 中 | 是 | 不进入 model_base；禁止用于校验金额/数量或推断真实价格。 |

## audit 字段

| field_name | 所在表 | 中文含义 | 字段来源 | 生成规则 | 取值范围或枚举 | 是否可进入 model_base | 是否默认进入 X_train | 是否为追溯键 | 是否为质量控制字段 | 是否存在标签泄漏风险 | 是否仅用于 audit/review | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| insurance_drug_code | audit | 药品医保编码 | 原始字段 | 原始医保编码标准化保留 | 字符串或缺失 | 否 | 否 | 否 | 是 | 低 | 是 | 不与 drug_code 合并。 |
| enterprise_code_raw | audit | 原始企业编码 | 原始字段 | 原始企业编码保留 | 字符串或缺失 | 否 | 否 | 否 | 是 | 低 | 是 | 企业编码不进 clean/model。 |
| hospital_level_detail_raw | audit | 医疗机构详细等级原始值 | 原始字段 | 原始详细等级文本保留 | 文本或缺失 | 否 | 否 | 否 | 是 | 低 | 是 | 仅供 audit，不作为主等级字段。 |
| drug_code_match_flag | audit | 当前行药品编码与医保编码是否一致 | 派生字段 | 当前行 `drug_code` 与当前行 `insurance_drug_code` 比较 | `1`=相等，`0`=不相等，`-1`=任一缺失无法比较 | 否 | 否 | 否 | 是 | 低 | 是 | `drug_code_match_flag 是行级一致性检查`；不代表 drug_code 在全局是否稳定。 |
| drug_code_conflict_flag | audit | 同一药品编码是否对应多个医保编码 | 派生字段 | 按 `drug_code` 分组，统计不同 `insurance_drug_code` 个数是否大于 1 | `1`=存在一对多冲突，`0`=未发现冲突，`-1`=drug_code 缺失无法判断 | 否 | 否 | 否 | 是 | 低 | 是 | `drug_code_conflict_flag 是同一 drug_code 对应多个 insurance_drug_code 的编码级冲突检查`；不同于行级相等检查。 |

## 订单状态字段枚举

| field_name | 枚举 | 中文说明 |
| --- | --- | --- |
| order_phase_code | `0` | unknown，未知或未映射 |
| order_phase_code | `10` | draft_or_plan，草稿或计划 |
| order_phase_code | `20` | submitted_or_pending，已下单或待处理；`已下发网采证明` 归入此类 |
| order_phase_code | `30` | confirmed，已确认 |
| order_phase_code | `40` | pending_dispatch，待配送 |
| order_phase_code | `50` | dispatched，已配送 |
| order_phase_code | `60` | received，已收货；`配送完成` 归入此类 |
| order_phase_code | `70` | invoiced_or_paid，已开票或已付款 |
| order_phase_code | `80` | completed，完成 |
| order_phase_code | `90` | returned_or_rejected，退货或拒收 |
| order_phase_code | `100` | cancelled_or_failed，取消或失败 |
| delivery_state_code | `0` | unknown，未知 |
| delivery_state_code | `1` | ordered_not_confirmed，已下单未确认 |
| delivery_state_code | `2` | confirmed_not_dispatched，已确认未配送 |
| delivery_state_code | `3` | dispatched_not_received，已配送未收货 |
| delivery_state_code | `4` | partially_dispatched，部分配送 |
| delivery_state_code | `5` | received，已收货 |
| delivery_state_code | `6` | completed_or_settled，完成或结算 |
| delivery_state_code | `7` | returned_or_rejected_receipt，退货或拒收 |
| delivery_state_code | `8` | cancelled_or_voided，取消或作废 |
| delivery_state_code | `9` | delivery_failed，配送失败 |
| order_terminal_flag | `1` | 明确终态 |
| order_terminal_flag | `0` | 明确非终态 |
| order_terminal_flag | `-1` | 不确定，需要人工复核或保守处理 |
| order_failure_flag | `1` | 失败/取消/拒绝/无法配送/退货等失败语义 |
| order_failure_flag | `0` | 正常推进状态 |
| order_failure_flag | `-1` | 不确定 |
| needs_manual_review | `True` | 状态或映射结果需要人工复核 |
| needs_manual_review | `False` | 暂不需要人工复核 |
| mapping_failure_reason | `unknown_or_unmapped_status` | `order_phase_code=0`，状态未知或未匹配 |
| mapping_failure_reason | `manual_review_status` | 状态命中人工复核规则 |
| mapping_failure_reason | 空字符串 | 暂未发现映射失败原因 |

## review 输出字段

### field_quality_gate_v2.csv

| field_name | 所在表 | 中文含义 | 字段来源 | 生成规则 | 取值范围或枚举 | 是否可进入 model_base | 是否默认进入 X_train | 是否为追溯键 | 是否为质量控制字段 | 是否存在标签泄漏风险 | 是否仅用于 audit/review | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| column | review_output | 被统计字段名 | 统计字段 | 来自 clean_v2 列名 | 字符串 | 否 | 否 | 否 | 是 | 低 | 是 | 字段质量门禁主键。 |
| null_count | review_output | 空值数量 | 统计字段 | 对 clean_v2 每列统计缺失数 | 非负整数 | 否 | 否 | 否 | 是 | 低 | 是 | 质量评估。 |
| null_rate | review_output | 空值率 | 统计字段 | `null_count / row_count` | 0 到 1 | 否 | 否 | 否 | 是 | 低 | 是 | 质量评估。 |
| distinct_count | review_output | 去重取值数 | 统计字段 | 对 clean_v2 每列统计 distinct | 非负整数 | 否 | 否 | 否 | 是 | 低 | 是 | 高基数字段需谨慎。 |
| dtype | review_output | pandas 数据类型 | 统计字段 | 读取 clean_v2 dtype | 字符串 | 否 | 否 | 否 | 是 | 低 | 是 | 供排错。 |
| sample_values | review_output | 样例值 | 统计字段 | 取少量非空样例 | 字符串 | 否 | 否 | 否 | 是 | 低 | 是 | 仅用于人工查看。 |
| in_model_base | review_output | 是否进入 model_base | 统计字段 | 判断字段名是否在 model_base 列中 | `True`/`False` | 否 | 否 | 否 | 是 | 低 | 是 | 字段职责检查。 |
| in_audit | review_output | 是否进入 audit | 统计字段 | 判断字段名是否在 audit 列中 | `True`/`False` | 否 | 否 | 否 | 是 | 低 | 是 | 字段职责检查。 |
| recommended_default_x_role | review_output | 推荐默认 X 角色 | 统计字段 | 追溯键/时间索引/质量 flag/candidate_base 规则打标 | `trace_key`、`time_index`、`quality_flag`、`candidate_base` | 否 | 否 | 否 | 是 | 中 | 是 | 只是门禁建议，不替代 feature view。 |

### numeric_desensitization_report_v2.csv

| field_name | 所在表 | 中文含义 | 字段来源 | 生成规则 | 取值范围或枚举 | 是否可进入 model_base | 是否默认进入 X_train | 是否为追溯键 | 是否为质量控制字段 | 是否存在标签泄漏风险 | 是否仅用于 audit/review | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| metric_group | review_output | 指标分组 | 统计字段 | 数值字段名、比例字段名、状态阶段或矛盾检查分组 | 字符串 | 否 | 否 | 否 | 是 | 低 | 是 | 如 `zero_rate`、`negative_rate`、ratio 字段名。 |
| metric | review_output | 指标名 | 统计字段 | 具体统计指标名称 | 字符串 | 否 | 否 | 否 | 是 | 低 | 是 | 包括 count/min/p25/p50/p75/p95/max/gt_1_rate。 |
| value | review_output | 指标值 | 统计字段 | 根据 metric 计算 | 数值 | 否 | 否 | 否 | 是 | 低 | 是 | `gt_1_rate` 使用非空 ratio 作为分母。 |

### numeric_negative_samples_v2.csv

| field_name | 所在表 | 中文含义 | 字段来源 | 生成规则 | 取值范围或枚举 | 是否可进入 model_base | 是否默认进入 X_train | 是否为追溯键 | 是否为质量控制字段 | 是否存在标签泄漏风险 | 是否仅用于 audit/review | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| row_uid | review_output | 负数样本行追溯键 | 原始字段 | 从负数行保留 | 字符串 | 否 | 否 | 是 | 是 | 低 | 是 | 用于回查。 |
| order_detail_id | review_output | 负数样本订单明细 ID | 原始字段 | 从负数行保留 | 字符串 | 否 | 否 | 是 | 是 | 低 | 是 | 用于回查。 |
| order_status_raw | review_output | 负数样本原始订单状态 | 原始字段 | 从负数行保留 | 文本 | 否 | 否 | 否 | 是 | 高 | 是 | 帮助判断负数是否业务合理。 |
| negative_field | review_output | 出现负数的字段名 | 统计字段 | 对数值字段逐列筛选 `<0` | 字符串 | 否 | 否 | 否 | 是 | 低 | 是 | 只用于质量核验。 |
| negative_value | review_output | 负数值 | 统计字段 | 对应 negative_field 的数值 | 数值 | 否 | 否 | 否 | 是 | 低 | 是 | 只用于质量核验。 |

### order_status_mapping_coverage.csv

| field_name | 所在表 | 中文含义 | 字段来源 | 生成规则 | 取值范围或枚举 | 是否可进入 model_base | 是否默认进入 X_train | 是否为追溯键 | 是否为质量控制字段 | 是否存在标签泄漏风险 | 是否仅用于 audit/review | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| metric | review_output | 覆盖率指标名 | 统计字段 | 汇总状态映射结果 | 字符串 | 否 | 否 | 否 | 是 | 中 | 是 | 包括 total_rows、mapped_rows、unmapped_rows、mapping_coverage 等。 |
| value | review_output | 覆盖率指标值 | 统计字段 | 按 metric 计算 | 数值或字符串 | 否 | 否 | 否 | 是 | 中 | 是 | 供人工判断映射是否充分。 |

### order_status_suspicious_mapping.csv

| field_name | 所在表 | 中文含义 | 字段来源 | 生成规则 | 取值范围或枚举 | 是否可进入 model_base | 是否默认进入 X_train | 是否为追溯键 | 是否为质量控制字段 | 是否存在标签泄漏风险 | 是否仅用于 audit/review | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| order_status_raw | review_output | 原始订单状态 | 原始字段 | 从 clean_v2 中筛出需复核状态 | 文本 | 否 | 否 | 否 | 是 | 高 | 是 | 用于人工复核。 |
| order_status_norm | review_output | 归一化订单状态 | 派生字段 | 对原始状态归一化 | 文本 | 否 | 否 | 否 | 是 | 高 | 是 | 用于定位映射项。 |
| order_phase_code | review_output | 生命周期阶段编码 | 映射字段 | 由状态映射表给出 | 见状态枚举 | 否 | 否 | 否 | 是 | 高 | 是 | 复核当前映射是否合理。 |
| delivery_state_code | review_output | 配送状态编码 | 映射字段 | 由状态映射表给出 | 见状态枚举 | 否 | 否 | 否 | 是 | 高 | 是 | 复核当前映射是否合理。 |
| needs_manual_review | review_output | 是否需要人工复核 | 映射字段 | 状态映射规则给出 | `True`/`False` | 否 | 否 | 否 | 是 | 中 | 是 | 复核筛选依据。 |
| mapping_failure_reason | review_output | 映射失败或复核原因 | 派生字段 | 根据状态映射结果生成 | 枚举或空字符串 | 否 | 否 | 否 | 是 | 中 | 是 | 解释为什么进入复核。 |
| count | review_output | 状态出现次数 | 统计字段 | 按状态分组计数 | 非负整数 | 否 | 否 | 否 | 是 | 低 | 是 | 供复核优先级排序。 |

### order_status_lifecycle_map.csv

| field_name | 所在表 | 中文含义 | 字段来源 | 生成规则 | 取值范围或枚举 | 是否可进入 model_base | 是否默认进入 X_train | 是否为追溯键 | 是否为质量控制字段 | 是否存在标签泄漏风险 | 是否仅用于 audit/review | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| status_keyword | review_output | 状态关键词 | 映射字段 | 手工维护的状态词或关键词 | 文本 | 否 | 否 | 否 | 是 | 高 | 是 | 生命周期映射依据。 |
| order_phase_code | review_output | 生命周期阶段编码 | 映射字段 | 手工维护映射 | 见状态枚举 | 否 | 否 | 否 | 是 | 高 | 是 | 映射表字段。 |
| order_phase_label | review_output | 生命周期阶段标签 | 映射字段 | 手工维护映射 | 文本 | 否 | 否 | 否 | 是 | 高 | 是 | 映射表字段。 |
| delivery_state_code | review_output | 配送状态编码 | 映射字段 | 手工维护映射 | 见状态枚举 | 否 | 否 | 否 | 是 | 高 | 是 | 映射表字段。 |
| delivery_state_label | review_output | 配送状态标签 | 映射字段 | 手工维护映射 | 文本 | 否 | 否 | 否 | 是 | 高 | 是 | 映射表字段。 |
| order_terminal_flag | review_output | 终态标记 | 映射字段 | 手工维护映射 | `1`/`0`/`-1` | 否 | 否 | 否 | 是 | 高 | 是 | 映射表字段。 |
| order_failure_flag | review_output | 失败标记 | 映射字段 | 手工维护映射 | `1`/`0`/`-1` | 否 | 否 | 否 | 是 | 高 | 是 | 映射表字段。 |
| needs_manual_review | review_output | 是否需要人工复核 | 映射字段 | 手工维护映射 | `True`/`False` | 否 | 否 | 否 | 是 | 中 | 是 | 映射表字段。 |
| review_reason | review_output | 复核原因 | 映射字段 | 手工维护或规则生成 | 文本或空 | 否 | 否 | 否 | 是 | 中 | 是 | 字段名以实际导出为准，含义为人工复核说明。 |

## bs_agent_dingdan_quality_report_v2.md

Markdown 质量报告不是结构化训练输入。它汇总以下内容：行数、列数、`row_uid` 唯一性、`order_detail_id` 唯一性和重复组数量、字段 null/distinct 质量入口、`region_dirty_flag` 分布、`raw_city_code` 与派生 `city_code` 冲突数量、`drug_code_match_flag` 分布、`drug_code_conflict_flag` 分布、状态映射覆盖率、`needs_manual_review` 分布、phase/delivery_state 分布、数值 zero/negative/ratio 质量、状态与数量矛盾、输出路径清单。
