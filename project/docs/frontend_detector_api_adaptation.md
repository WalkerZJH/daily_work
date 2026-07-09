# Frontend Detector API Adaptation Guide

## Purpose

This note tells the frontend which backend APIs to adapt after the project-side
detector result table integration.

The frontend must keep using project APIs only:

```text
front_end -> project API -> risk_model_core -> result-batch tables
```

Do not read `risk_model_core`, result-batch files, `algo_main`, or static algorithm
outputs directly from the frontend.

## Product Message

Daily page changes come from daily rule inspection results, not from daily model
probability changes.

- Monthly model probability remains stable inside the monthly `risk_result_batch`.
- `detector_score` is a rule inspection score, not loss probability.
- Daily detector clues are rule clues. They do not create new model high-risk entities.
- Non-monthly-high-risk clues must be labeled as daily rule clues, not model high risk.
- Reserved, experimental, and interface-only detectors must stay visually disabled or marked as not fully launched.

## APIs To Adapt

### Detector Readiness

`GET /api/v1/daily-detector/status`

Use this for daily detector readiness indicators.

Expected fields:

- `ready`
- `run_date`
- `source`
- `warnings`

If `ready=false`, show an empty or pending state. Do not fall back to result-batch
file reads.

### Detector Catalog

`GET /api/v1/detectors/catalog`

Use this for detector status display and disabled-state explanations.

Important fields:

- `detector_id`
- `detector_family`
- `detector_name`
- `status`
- `enabled_by_default`
- `method`
- `output_schema_version`
- `caveat`

Frontend status handling:

- `implemented`: available.
- `interface_only`: show but disable launch-style interactions.
- `experimental`: show as internal or trial capability.
- `reserved`: disabled by default.

### Detector Runs

`GET /api/v1/detectors/runs`

Use this for latest run display and optional run selection.

Supported query params:

- `report_month`
- `run_date`
- `limit`

Important fields:

- `detector_run_id`
- `run_date`
- `report_month`
- `source_result_batch_id`
- `detector_config_version`
- `enabled_detectors`
- `scanned_entity_count`
- `clue_count`
- `attached_high_risk_count`

### All Daily Rule Clues

Preferred endpoint:

`GET /api/v1/detectors/clues`

Compatibility endpoint:

`GET /api/v1/daily-detector/clues`

Use this for the "all rule clues" page.

Supported filters:

- `detector_run_id`
- `run_date`
- `detector_id`
- `detector_family`
- `manufacturer_code`
- `hospital_code`
- `drug_group`
- `only_monthly_high_risk`
- `page`
- `page_size`

Important fields:

- `detector_clue_id`
- `detector_score`
- `detector_level`
- `confidence`
- `hit_flag`
- `root_cause_label`
- `evidence_text`
- `is_monthly_high_risk_entity`
- `risk_entity_id`
- `monthly_risk_probability`
- `monthly_loss_value`
- `caveat`

Display rules:

- Render `detector_score` as "规则巡检分".
- Do not render `detector_score` as probability or percent risk.
- If `is_monthly_high_risk_entity=false`, label the row as "今日规则线索".
- Do not route non-monthly-high-risk clues into the monthly risk entity list.

### Risk Entity Detector Evidence

`GET /api/v1/risk-entities/{risk_entity_id}/detector-evidence`

Use this on risk entity detail pages to show attached detector evidence for an
existing monthly risk entity.

Important fields:

- `risk_entity_id`
- `monthly_risk_probability`
- `monthly_loss_value`
- `items`
- `catalog_by_detector_id`
- `semantic_caveats`

Each evidence item includes:

- `detector_id`
- `detector_family`
- `detector_score`
- `confidence`
- `root_cause_label`
- `evidence_text`
- `caveat`

If the `risk_entity_id` does not exist, the API returns 404. The frontend should
not create a detail page from a daily clue alone.

### Detector Config Status

`GET /api/v1/detectors/config-status`

Use this for internal configuration pages or admin messaging only.

Important fields:

- `effective_config_version`
- `latest_run_id`
- `latest_run_date`
- `pending_config_version`
- `pending_config_exists`
- `pending_config_supported`
- `next_run_required`
- `history_rewrite_allowed`
- `config_edit_semantics`

Required UI message:

```text
配置修改只在下一次 detector 巡检运行后生效；历史 detector 结果不会被静默改写。
```

Do not expose full detector hyperparameters on business-facing pages.

## Existing Page API Implications

### Workbench

`GET /api/v1/workbench`

Keep this as the monthly high-risk workbench. It should not include every daily
detector clue. It can show detector summaries such as latest run date and clue
counts once the frontend has a design slot for them.

The UI label for value ranking should be "损失价值". Prefer `loss_value` or
`monthly_loss_value` when present. Existing `business_score` should be treated as
a deprecated compatibility value and not displayed as "业务评分".

### Risk Entities List

`GET /api/v1/risk-entities`

Keep this as the monthly risk entity list. Do not mix non-monthly-high-risk daily
detector clues into this list. Use `/api/v1/detectors/clues` for the all-clues
page.

### Risk Entity Detail

`GET /api/v1/risk-entities/{risk_entity_id}`

Keep existing monthly detail behavior. Add a detector evidence panel by calling:

`GET /api/v1/risk-entities/{risk_entity_id}/detector-evidence`

## Components To Add Or Adjust

- Daily detector status badge: uses `/api/v1/daily-detector/status`.
- Detector capability/status panel: uses `/api/v1/detectors/catalog`.
- All rule clues table: uses `/api/v1/detectors/clues`.
- Risk detail detector evidence panel: uses `/api/v1/risk-entities/{risk_entity_id}/detector-evidence`.
- Internal config status notice: uses `/api/v1/detectors/config-status`.
- Remove or hide customer-page "模型关键指标" component unless an internal admin route explicitly needs it.

## Copy Guardrails

Allowed wording:

- "规则证据命中"
- "规则巡检分"
- "今日规则线索"
- "建议复核采购节奏"
- "该 detector 当前为保留能力"
- "参数修改将在下一次 detector 巡检后生效"

Forbidden wording:

- "detector_score 表示流失概率"
- "规则巡检分表示业务紧迫性"
- "医院确定流失"
- "一定不会再采购"
- "配送商责任已确认"
- "竞品替代已确认"

## Frontend Acceptance Checklist

- Frontend calls only project APIs.
- `detector_score` is never named probability.
- All-clues page can show non-monthly-high-risk clues.
- Non-monthly-high-risk clues do not appear in monthly risk entity list.
- Risk detail detector evidence is fetched only for an existing `risk_entity_id`.
- Catalog visually distinguishes `implemented`, `interface_only`, `experimental`, and `reserved`.
- Customer-facing pages no longer show model evaluation metrics by default.
