# Health 页面说明

当前 health 页面是“日报式算法探查页”，用于验证算法链路，不是正式工单页、驾驶舱或预警流转页面。

页面调用顺序：

1. `GET /api/v0/options/enterprises`
2. `GET /api/v0/options/provinces`
3. `GET /api/v0/options/product-lines`
4. `GET /api/v0/options/detector-categories`
5. `GET /api/v0/options/detectors?category=...`
6. 用户选择 `as_of_date`、`lookback_days`、`baseline_days`、企业、省份、产品线、category、detector。
7. `POST /api/v0/detectors/{detector_id}/run` 或 `POST /api/v0/detectors/run-by-category`

页面必须展示：

- 本次运行日期 `as_of_date`
- 回看窗口 `lookback_days`
- 基线窗口 `baseline_days`
- 数据范围
- 命中数
- 未命中原因
- warnings
- evidence_items
- sample_order_ids
- 后端返回的固定中文 `narrative`

企业、省份、产品线必须通过 options API 下拉选择，不要求用户手输 code。当前所有结果仅用于算法验证，未经过真实回测和概率校准，不能作为正式业务预警。
