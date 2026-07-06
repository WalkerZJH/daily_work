# BS_Agent_DingDan v2 清洗质量报告

## 一、处理范围

- 清洗表行数：100000
- clean_v2 字段数：47
- model_base 行数/字段数：100000 / 31
- audit 行数/字段数：100000 / 39

## 二、主键与重复检查

- row_uid 是否唯一：True
- order_detail_id 是否唯一：True
- order_detail_id 重复行数：0

## 三、字段质量

字段级 null 数、null 率、distinct 数请查看 `field_quality_gate_v2.csv`。

## 四、地区字段检查

- region_dirty_flag=0: 99457
- region_dirty_flag=1: 543

## 五、药品编码检查

drug_code 与 insurance_drug_code 一致性：
- drug_code_match_flag=0: 23214
- drug_code_match_flag=1: 76786

drug_code 与 insurance_drug_code 冲突情况：
- drug_code_conflict_flag=0: 88176
- drug_code_conflict_flag=1: 11824

## 六、订单状态映射

- 总行数：100000.0
- 已映射行数：98616.0
- 未映射行数：1384.0
- 映射覆盖率：0.98616

需要人工复核：
- needs_manual_review=False: 98616
- needs_manual_review=True: 1384

订单阶段分布：
- order_phase_code=0: 1384
- order_phase_code=10: 129
- order_phase_code=20: 5658
- order_phase_code=30: 29870
- order_phase_code=40: 2862
- order_phase_code=50: 5106
- order_phase_code=60: 43620
- order_phase_code=70: 3127
- order_phase_code=80: 994
- order_phase_code=90: 79
- order_phase_code=100: 7171

配送状态分布：
- delivery_state_code=0: 1384
- delivery_state_code=1: 5787
- delivery_state_code=2: 32732
- delivery_state_code=3: 4974
- delivery_state_code=4: 132
- delivery_state_code=5: 43620
- delivery_state_code=6: 4121
- delivery_state_code=7: 79
- delivery_state_code=8: 4139
- delivery_state_code=9: 3032

## 七、数值字段检查

zero rate、negative rate、比例分布、gt_1_rate 请查看 `numeric_desensitization_report_v2.csv`。

注意：`gt_1_rate` 使用非空 ratio 行作为分母。

## 八、状态与数量矛盾

- received_but_arrival_quantity_zero: 4755.0
- dispatched_but_delivery_quantity_zero: 320.0
- cancelled_or_failed_but_has_delivery_or_arrival: 283.0

## 九、model_base 使用说明

- `model_base` 是稳定的建模基础表，不是最终 `X_train`。
- `row_uid` 和 `order_detail_id` 是追溯键，不应直接进入 X。
- `purchase_time` 是排序、切分、聚合用的时间索引，不应作为普通连续数值特征直接进入 X。
- `region_dirty_flag` 是质量控制字段，默认不进入 X。
- 状态语义字段在完成、失败、终止、到货、配送质量等任务中可能造成标签泄漏。
- `delivery_rate`、`arrival_rate` 等比例字段来自数量字段，不是配送时长特征。
- 禁止使用 金额 / 数量 推断真实单价，也禁止使用采购价校验金额 / 数量。

## 十、输出路径

- review_outputs.clean_sample_v2: C:\Users\admin\Myprojects\for_git\algo_main\exports\clean\bs_agent_dingdan_clean_sample_v2.csv
- review_outputs.audit_sample: C:\Users\admin\Myprojects\for_git\algo_main\exports\clean\bs_agent_dingdan_audit_sample.csv
- review_outputs.field_quality_gate_v2: C:\Users\admin\Myprojects\for_git\algo_main\exports\eda\field_quality_gate_v2.csv
- review_outputs.numeric_desensitization_report_v2: C:\Users\admin\Myprojects\for_git\algo_main\exports\eda\numeric_desensitization_report_v2.csv
- review_outputs.order_status_mapping_coverage: C:\Users\admin\Myprojects\for_git\algo_main\exports\eda\order_status_mapping_coverage.csv
- review_outputs.order_status_suspicious_mapping: C:\Users\admin\Myprojects\for_git\algo_main\exports\eda\order_status_suspicious_mapping.csv
- review_outputs.order_status_lifecycle_map: C:\Users\admin\Myprojects\for_git\algo_main\exports\mappings\order_status_lifecycle_map.csv
- model_base.parquet: C:\Users\admin\Myprojects\for_git\algo_main\data\03_cleaned\bs_agent_dingdan_model_base.parquet
