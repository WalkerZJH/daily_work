# Detector Release B implementation

Implemented on 2026-07-16 under the isolation boundary in `reports/release_b_active_materialization_boundary.md`.

## Outcome

Release B completes the Detector clue browsing and entity evidence views without changing Detector computation, Release A materialization, monthly candidate generation, observation registry publication, or active 2025 output paths.

## Backend

- `CompositeDetectorResultRepository` and single-component Detector repositories can read display names only from the exact probability repository selected by `ReportContextService`.
- Display lookup joins normalize string keys and use the exact manufacturer, hospital, and drug identity. Clues obtain `drug_code` from the matching immutable `daily_detector_results.detector_result_id`; legacy `drug_group` is not treated as a `drug_code` alias.
- Detector Catalog is the authoritative source for Chinese name, English name, Chinese family name, and short business description. All 10 implemented Detector ids have stable values.
- New read-only `GET /api/v1/detectors/entity-detail` requires `observation_date`, `manufacturer_code`, `hospital_code`, and `drug_code`.
- The endpoint returns every hit Detector result for that exact daily entity. `clue_id` is optional traceability metadata and does not narrow the entity evidence set.
- Monthly prediction and trend are optional. They are returned only when the exactly associated probability batch contains one matching recurring identity; no latest-month, alternate-date, or candidate fallback is used.
- The existing `GET /api/v1/detectors/clues/{clue_id}` route remains available. Old clue-only links first resolve that technical record to the full entity key, then load the entity-level detail.

## Frontend

- The attached design at `daily_work/notes/new_ver/前端美化/clues页面美化策略（待实现）.md` was read in full and used as the Clues filter interaction authority.
- The two Detector dropdowns were replaced by four category cards and Catalog-backed Detector subcards.
- Expanding a category is Draft-only and sends no request. Query-all, query-category, and query-Detector actions explicitly apply filters.
- Disabled and reserved Catalog entries remain visible with a non-queryable state.
- The card panel uses button semantics, `aria-expanded`, focus styles, responsive layouts, scoped CSS, and reduced-motion support.
- The result list keeps its existing API, pagination, sort, evidence columns, and result location. Names are primary; exact codes are secondary. Rule inspection score is secondary copy rather than a primary table column.
- Count copy distinguishes the daily hit-record count from the current filtered result count and explains that one entity can hit multiple rules.
- List detail links carry the full entity key. Entity detail shows all daily hits, exact display names, optional monthly context, and optional trend. Old clue-only detail remains compatible.
- Entity detail includes a Detector summary, one evidence card per hit, current/baseline/comparison/threshold values, hit reason, caveat, and collapsible immutable calculation/configuration context.

## Boundaries preserved

- No Detector was run, restarted, stopped, or published.
- No active 2025 staging, Parquet, manifest, or registry output was written. The full-suite read-only deviation recorded in `release_b_active_materialization_boundary.md` is the sole boundary exception.
- No observation registry file was changed.
- No monthly model score, candidate, probability, amount, or ranking logic was changed.
- Detector Score remains labeled as a rule inspection score, never as probability.
- Clues remains a rule-only inspection page; monthly data appears only in the entity detail context and may be unavailable.

## API verification

Fixture-only FastAPI OpenAPI verification confirmed the clues list, entity detail, risk-entity Detector evidence, and monthly probability trend routes. No existing uvicorn process was restarted.

## Unfinished items

No Release B functional item remains. Release C cross-day aggregation is intentionally excluded. Overall compliance remains partial because the earlier full-suite run caused the read-only active-path deviation recorded in the boundary report; that historical action cannot be undone.
