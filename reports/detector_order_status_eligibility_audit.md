# Detector 订单状态准入审计

- 清洗输入批次：`cleaned-detector-facts-v2-20260716`
- 清洗契约：`cleaned_detector_input_v1`
- 订单总行数：827,784
- 正常完成且允许进入 Detector：514,583
- 排除行数：313,201
- 唯一准入条件：`order_phase_code in (60, 70, 80) AND terminal=1 AND failure=0 AND needs_manual_review=false`
- 每个 Detector 均复用同一过滤器；不存在各规则自行维护状态关键词。

## 分阶段统计

| order_phase_code | detector_order_eligible | detector_exclusion_reason | count |
| --- | --- | --- | --- |
| 0 | False | not_terminal | 25146 |
| 10 | False | not_terminal | 910 |
| 20 | False | not_terminal | 16984 |
| 30 | False | not_terminal | 71139 |
| 40 | False | not_terminal | 40786 |
| 50 | False | not_terminal | 106207 |
| 60 | True | eligible_normal_completion | 500916 |
| 70 | True | eligible_normal_completion | 7451 |
| 80 | True | eligible_normal_completion | 6216 |
| 90 | False | failure_or_cancelled_terminal | 425 |
| 100 | False | failure_or_cancelled_terminal | 51604 |

行级组合矩阵见 `reports/detector_order_status_eligibility_matrix.parquet`。
