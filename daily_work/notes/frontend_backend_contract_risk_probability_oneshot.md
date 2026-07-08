# 前端需要的后端接口契约：风险概率、detector 详情与 oneshot 复购倾向

本文件给后端 Codex 线程使用。前端当前已按以下数据契约完成页面适配，后端实现接口时优先保证字段语义和命名稳定。

## 1. RiskEntity 列表

接口：`GET /api/v1/risk-entities`

用途：月报工作台与风险实体清单。前端用 `business_score` 降序排序。

核心字段：

```json
{
  "report_month": "2026-07",
  "score_batch_id": "2026-07-monthly-risk-algorithm-fixture",
  "score_as_of_date": "2026-07-31",
  "entities": [
    {
      "entity_id": "re_huaxi_c_h6",
      "hospital_name": "四川大学华西医院",
      "drug_name": "C产品线 · 肿瘤",
      "manufacturer_id": "M001",
      "region": "西南",
      "horizon": "H6",
      "risk_probability": 0.74,
      "average_consumption_in_window": 1950000,
      "business_score": 1443000,
      "risk_band": "high",
      "last_purchase_date": "2026-04-18",
      "days_since_last_purchase": 80,
      "risk_card_count": 5,
      "status": "优先跟进",
      "primary_reason": "连续停购苗头叠加配送履约恶化，需要判断需求流失还是断供问题。"
    }
  ]
}
```

排序公式：`business_score = risk_probability * average_consumption_in_window`。

## 2. RiskEntity detector 详情

接口：`GET /api/v1/risk-entities/{entity_id}/detectors`

用途：风险实体详情页。入选 entity 后，前端展示所有 detector 的计算结果，并保留 XGBoost SHAP 与 detector 自然语言聚合位置。

核心字段：

```json
{
  "entity_id": "re_huaxi_c_h6",
  "risk_probability": 0.74,
  "average_consumption_in_window": 1950000,
  "business_score": 1443000,
  "detector_results": [
    {
      "detector_id": "gap",
      "detector_name": "采购间隔 detector",
      "score": 0.88,
      "signal": "强命中",
      "status": "采购间隔超期",
      "evidence": "当前间隔 80 天，历史中位间隔 31 天。",
      "action": "优先确认院内采购计划是否暂停。"
    }
  ],
  "xgboost_shap": [
    {
      "feature": "avg_consumption_h6",
      "contribution": 0.24,
      "explanation": "预测窗口内平均消费金额高，放大业务优先级。"
    }
  ],
  "detector_narrative": "detector 结果自然语言聚合：高消费基线叠加采购间隔和配送履约信号，使该实体在业务评分排序中位列第一。"
}
```

建议 detector 覆盖：采购间隔、频次下降、品规收缩、配送履约、终端动态、数量变化。前端希望返回全量 `detector_results`，包括弱信号和平稳项，便于详情页完整呈现。

## 3. Oneshot 新进终端监测

接口：`GET /api/v1/oneshot-terminals`

用途：左侧边栏“新进终端监测”。前端汇报本期 oneshot 数量、复购倾向、预计复购金额和首采信息。

核心字段：

```json
{
  "report_month": "2026-07",
  "summary": {
    "oneshot_count": 6,
    "high_repurchase_propensity_count": 3,
    "average_repurchase_propensity": 0.67,
    "expected_repurchase_amount": 1520000
  },
  "items": [
    {
      "oneshot_id": "os_001",
      "hospital_name": "浙江大学医学院附属第一医院",
      "drug_name": "D产品线 · 消化",
      "region": "华东",
      "first_purchase_date": "2026-06-18",
      "first_purchase_amount": 320000,
      "days_since_first_purchase": 19,
      "repurchase_propensity": 0.79,
      "expected_repurchase_amount": 410000,
      "priority": "高复购倾向",
      "reason": "首采金额高，首采后 19 天内出现补货咨询，所在区域同类终端 H6 复购表现强。"
    }
  ]
}
```

## 4. 前端页面依赖关系

- `index.html`：展示风险概率、业务评分公式和高价值 entity 队列。
- `clues.html`：按 `business_score` 排序展示 RiskEntity。
- `clue-detail.html`：展示所有 `detector_results`、`xgboost_shap`、`detector_narrative`。
- `oneshot.html`：展示 oneshot 新进终端监测与 `repurchase_propensity`。
- `algo-architecture.html`：解释主干概率、业务评分排序、detector 详情和 oneshot 复购倾向算法。
