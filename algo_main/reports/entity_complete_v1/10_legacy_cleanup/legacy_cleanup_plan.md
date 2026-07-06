# Legacy cleanup plan

status: skipped_due_to_active_consolidation

A running scripts/run_entity_complete_algorithm_consolidation_v1.py process is still writing reports/entity_complete_v1/07_algorithm_consolidation/algorithm_consolidation_progress.md. This run does not delete legacy artifacts and does not modify 07_algorithm_consolidation.

## Candidate cleanup scope

- Candidate legacy cleanup rows: 42
- Protected current-chain/audit rows: 5
- Delete decision this run: deferred
- Current replacement chain: entity_complete_v1

After the active consolidation task exits and the worktree is stable, delete only manifest rows where delete_allowed=true and reason is legacy_dirty_result or legacy_dirty_data.

Protected classes: entity_complete_v1, reset_entity_complete_rebuild_v1, sql_sampling_integrity_audit_v1, 09_m_module_implementation_audit, source code, tests, configs, notebooks, and design documents.
