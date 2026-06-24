# API

Base service remains `terminal_guard_algo_backend`; API prefix is `/api/v0`.

## Inspection

`POST /api/v0/inspection/dry-run`

Request extends the previous CSV shape:

```json
{
  "source_type": "csv",
  "dataset_name": "sample",
  "csv_path": null,
  "as_of_date": "2026-06-24",
  "user_id": "admin",
  "enterprise_code": null,
  "province": null,
  "province_code": null,
  "row_limit": null
}
```

`source_type` is `"csv"` by default for compatibility. Use `"database"` to read `DATABASE_URL` with `SQLTableSourceAdapter`. Database dry-run applies the effective user's province scope unless a narrower province is already supplied.

Response includes:

- `risk_card_candidates`: deterministic `RiskCardCandidate` list for downstream clue management.
- `top_risk_clues`: compatibility field containing the same candidates.
- `detector_hit_distribution`, `warning_summary`, `backbone`.

`rule_score` and `risk_score_deprecated` are uncalibrated sorting signals only. They are not probabilities.

## Detector Catalog

`GET /api/v0/detectors/catalog`

Returns all detector metadata: `detector_id`, `category`, `family`, `version`, `required_features`, `required_columns`, `implemented`, and `enabled_by_default`.

## User Config

`GET /api/v0/users/me/config`

Reads `X-User-Id`; defaults to `admin` for dev/local use. Returns permission, preference, and effective detector config.

`PATCH /api/v0/users/{user_id}/preferences`

Updates only preference:

```json
{
  "enabled_detectors": ["ip_interval", "inactive_terminal"]
}
```

Admin can edit any user. Non-admin users can edit only themselves. Enabling a detector outside category permission returns `403`.

`GET /api/v0/config/effective?user_id=js_manager_001`

Returns the merged effective detector config after permission filtering.
