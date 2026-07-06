# Reset Cleanup Plan

## Purpose

The old alive-prediction derived artifacts were built on a row-level TOP N SQL sample. They must not be reused as algorithm conclusions for `entity_complete_v1`.

## Allowed Stale Derived Directories

- `data/03_cleaned`
- `data/04_facts`
- `data/05_features`
- `cache`
- `exports/clean`
- `exports/eda`
- `exports/mappings`

## Planned Action

- Archive non-`.gitkeep` files to `archive/stale_pre_entity_complete_reset/`.
- Preserve source code, configs, notebooks, docs, `.env`, design documents, and SQL sampling audit reports.
- Keep old reports in place as stale historical evidence; new conclusions go under `reports/entity_complete_v1/`.

## Manifest Counts

- files planned for archive: 45
- placeholder files preserved: 6
- missing allowed directories: 1
