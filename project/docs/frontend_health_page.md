# Health 页面说明

当前 health 页面是日报式算法探查页，用于验证算法链路是否可运行，不是正式工单页、派单页、驾驶舱或业务闭环页面。

## 主干算法 smoke test 展示口径

页面必须展示：

- 数据源 `source_type`，支持 `database` / `csv`
- 检测日期 `as_of_date`
- 回看窗口 `lookback_days`
- 基线窗口 `baseline_days`
- 可选 `history_start_date`
- 企业、省份、产品线筛选

P_alive 展示文案应使用：

- 读取订单行数
- 有效订单行数
- 分析单元数
- P_alive 预测结果数
- 预测口径：每个 医院×产品线 在检测日期输出 1 条 P_alive

不得使用“在 X 行数据中进行了 Y 次预测”这类容易误解为逐订单预测的文案。

如果 `prediction_count == analysis_unit_count`，页面显示“口径正常”。如果不一致，页面显示后端 warning，尤其是 `BACKBONE_UNIT_COUNT_INCONSISTENT`。

## Detector 探查展示

页面调用顺序：

1. `GET /api/v0/options/enterprises`
2. `GET /api/v0/options/provinces`
3. `GET /api/v0/options/product-lines`
4. `GET /api/v0/options/detector-categories`
5. `GET /api/v0/options/detectors?category=...`
6. 用户选择 `as_of_date`、`lookback_days`、`baseline_days`、企业、省份、产品线、category、detector。
7. `POST /api/v0/detectors/{detector_id}/run` 或 `POST /api/v0/detectors/run-by-category`

页面展示后端返回的 `metrics`、`evidence_items`、`sample_order_ids`、`warnings`、`debug_features` 和固定中文 `narrative`。核心业务解释由后端生成，前端不自行拼接。

## 下拉选项

企业、省份、产品线必须通过 options API 下拉选择，不要求用户手输 code。

## debug_features

列表默认不展开完整 `debug_features`。只有用户勾选完整调试字段或进入详情时，才显示完整特征，避免表格列数爆炸。

## 边界

所有结果仅用于算法验证，未经过真实回测和概率校准，不能作为正式业务预警。当前不实现正式工单、Agent、自动调度、完整增量更新或自动训练。
