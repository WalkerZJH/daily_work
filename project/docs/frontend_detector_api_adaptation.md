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
- Customer-facing pages show `risk_probability`, `average_consumption_in_window`, and `loss_value`.
- Customer-facing pages should not show `monthly_loss_value`, `business_score`, `expected_loss`, or `fill_policy`.
- `involved_amount` means consumption amount inside the selected H3/H6/H12 horizon window, not full-history amount.
- `detector_score` is a rule inspection score, not loss probability.
- Daily detector clues are rule clues. They do not create new model high-risk entities.
- Non-monthly-high-risk clues must be labeled as daily rule clues, not model high risk.
- Reserved, experimental, and interface-only detectors must stay visually disabled or marked as not fully launched.

## APIs To Adapt

### Report Context

`GET /api/v1/report-context`

Use this before loading date-sensitive pages, or rely on the same `report_context`
object embedded in page APIs.

Supported query params:

- `observation_date`
- `report_month`
- `run_date`，旧兼容参数，等价映射为 `observation_date`
- `horizon`
- `manufacturer_code`
- `user_id`

Important fields:

- `observation_date`
- `probability_report_month`
- `probability_batch_available`
- `detector_run_date`
- `detector_run_available`
- `context_status`
- `manual_selection_required`
- `requested_horizon`
- `effective_horizon`
- `available_report_months`
- `available_detector_run_dates`
- `available_horizons`

Frontend rule:

- `observation_date` is the date the user is viewing.
- `probability_report_month` is the most recent complete calendar month before
  `observation_date`.
- `detector_run_date` is the rule inspection date and should equal
  `observation_date`.
- If `detector_run_available=false`, render a partial/empty detector state.
- Do not substitute a different detector date silently.

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
- `caveat`

Display rules:

- Render `detector_score` as "规则巡检分".
- Do not render `detector_score` as probability or percent risk.
- Do not display `monthly_loss_value`, `business_score`, `expected_loss`, or `fill_policy` on customer pages even if a compatibility payload contains them.
- If `is_monthly_high_risk_entity=false`, label the row as "今日规则线索".
- Do not route non-monthly-high-risk clues into the monthly risk entity list.

### Risk Entity Detector Evidence

`GET /api/v1/risk-entities/{risk_entity_id}/detector-evidence`

Use this on risk entity detail pages to show attached detector evidence for an
existing monthly risk entity.

Important fields:

- `risk_entity_id`
- `monthly_risk_probability`
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

Use this as the monthly high-risk workbench and the frontend's primary page
source.

Supported query params:

- `manufacturer_code`
- `report_month`
- `run_date`
- `horizon=H3|H6|H12`
- `top_n`
- `sort_by=loss_value|risk_probability|detector_score|involved_amount`

Behavior:

- Every response includes `report_context` and requested/effective date fields.
- It should not include every daily detector clue.
- It returns monthly risk entities using the selected `horizon`.
- It can show detector summaries such as latest run date and clue counts.
- It must not display `monthly_loss_value`, `business_score`, `expected_loss`, `fill_policy`, or model metrics.
- It may display `loss_value`, which is computed from `risk_probability` multiplied by `average_consumption_in_window`; if the amount proxy is missing, the backend returns `loss_value=0` with `loss_value_status=amount_proxy_missing`.
- `sort_by=involved_amount` sorts by selected horizon window involved amount.

### Risk Entities List

`GET /api/v1/risk-entities`

Keep this as the monthly risk entity list. It accepts the same customer-facing
query params as `/api/v1/workbench`: `manufacturer_code`, `report_month`,
`run_date`, `horizon`, `top_n`, and `sort_by`. It uses effective dates from
`report_context`. Do not mix non-monthly-high-risk daily detector clues into this
list. Use `/api/v1/detectors/clues` for the all-clues page.

### Risk Entity Detail

`GET /api/v1/risk-entities/{risk_entity_id}?horizon=H6`

Use this for monthly risk entity detail. The selected horizon controls the
displayed probability, involved amount, risk band, and reason summary. Add a
detector evidence panel by calling:

`GET /api/v1/risk-entities/{risk_entity_id}/detector-evidence`

The detector evidence endpoint supports `run_date`, `detector_family`, and
`detector_id` filters.

### Probability Trend

`GET /api/v1/risk-entities/{risk_entity_id}/probability-trend?horizon=H6`

Use this for trend charts. It returns one series for the selected horizon with
`report_month`, `risk_probability`, and `involved_amount`.

### Manufacturer Options

`GET /api/v1/my/manufacturers`

Use this to populate manufacturer selectors. The backend resolves current-user
scope and returns only visible manufacturers. The endpoint also accepts
`report_month`, `run_date`, `horizon`, `manufacturer_code`, and `user_id`, and
returns report-context fields for consistent page state.

### Daily Detector Date Options

`GET /api/v1/daily-detector/dates`

Use this to populate daily report date selectors. These dates refer to detector
inspection runs and do not imply monthly model probability recalculation.

`GET /api/v1/daily-detector/status` and
`GET /api/v1/daily-detector/clues` also accept `observation_date`. If that
detector run does not exist, they return `200` with `ready=false`,
`context_status=detector_run_unavailable`, `total=0`, and `items=[]`; the
frontend should render a partial/empty state, not mock rows or request a
different date.

## Components To Add Or Adjust

- Daily detector status badge: uses `/api/v1/daily-detector/status`.
- Report/date fallback banner: uses `/api/v1/report-context` or embedded `report_context`.
- Daily detector date selector: uses `/api/v1/daily-detector/dates`.
- Manufacturer selector: uses `/api/v1/my/manufacturers`.
- Detector capability/status panel: uses `/api/v1/detectors/catalog`.
- All rule clues table: uses `/api/v1/detectors/clues`.
- Risk detail detector evidence panel: uses `/api/v1/risk-entities/{risk_entity_id}/detector-evidence`.
- Risk probability trend chart: uses `/api/v1/risk-entities/{risk_entity_id}/probability-trend`.
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
- Customer-facing pages show `loss_value` but do not show `monthly_loss_value`, `business_score`, `expected_loss`, or `fill_policy`.
- H3/H6/H12 switching uses backend `horizon` query params instead of frontend-local recalculation.
- `involved_amount` is displayed as the selected horizon window amount.
