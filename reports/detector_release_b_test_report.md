# Detector Release B test report

Run date: 2026-07-16 (Asia/Shanghai)

## Release B isolation suite

Command:

`python -m pytest project/tests/test_detector_release_b_entity_detail.py project/tests/test_detector_release_b_frontend_contract.py project/tests/test_detector_clue_detail_api.py project/tests/test_detector_clues_pagination.py project/tests/test_daily_detector_clue_display_lookup.py project/tests/test_daily_detector_clues_api.py project/tests/test_detector_result_clues_api.py -q`

Result: **28 passed, 0 failed**.

Covered:

- exact entity key and exact observation-date filtering;
- old clue-only URL resolution into the complete entity key;
- multiple Detector hits for one entity;
- Detector-only entity with no monthly candidate;
- optional exact monthly prediction and trend;
- display-name lookup delegation from daily components to the associated monthly batch;
- code fallback when a name is unavailable;
- stable Chinese Catalog fields for all 10 implemented Detector ids;
- the stable `YL221606` / `ZA12AAN0014010203711` sample names and leading-zero code preservation;
- OpenAPI discovery and manufacturer-key isolation;
- clue-only detail backward compatibility;
- full entity-key navigation;
- Draft/Applied card interaction contract;
- accessibility and reduced-motion source contract;
- clue pagination, API mapping, and display lookup regression.

Warnings were non-failing: Starlette `TestClient` deprecation, a pandas future warning in existing component concatenation, and a denied pytest cache directory on this Windows workspace.

## Frontend production build

Command: `npm run build` in `front_end`.

Result: **passed** with Vite 8.1.2; 46 modules transformed and all HTML entry points emitted.

## Full project suite

Command: `python -m pytest project/tests -q`.

Result: **203 passed, 7 failed**.

The seven failures are outside the Release B changes:

- two “missing Detector date” tests observed ready data in the currently configured formal data environment;
- one frontend page test expected non-empty default entities;
- one existing workbench 422 contract rejects the additional `allowed_sort_by` field already returned by the application;
- one formal-mode manufacturer test observed a conditional scope response;
- two workbench tests conflict over manufacturer scope and availability of `detector_score` sorting.

Release B did not modify those workbench/default-payload paths. No attempt was made to mutate active data, mask environment-backed readiness, or change Release A/workbench behavior solely to satisfy them.

Boundary note: the full suite should not have been run under the strict active-materialization boundary because two existing tests point directly at `data/project_result_batches` and issued read-only queries for `2025-12-05`. This deviation was discovered from the failure trace and test helper, then recorded in `release_b_active_materialization_boundary.md`. The Release B isolation suite itself remained fixture-only.

The full suite was not rerun during the continuation pass. Only the 28 fixture/temporary-directory Release B tests and the frontend build were executed.
