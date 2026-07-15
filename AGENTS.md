# Long-running batch safety

Before starting or restarting a monthly result-batch materialization, inspect the target `report_month` and `run_id` for an existing formal directory, a hidden `.staging-*` directory, and a live matching process. If a matching process or staging directory exists, monitor it and do not start another materialization unless the user explicitly authorizes a restart after the prior process has ended or been diagnosed as failed. Never run concurrent materializations for the same target batch.

Do not delete, overwrite, or reuse an existing formal batch directory. A retry must use a new versioned `run_id` and preserve the prior staging directory for diagnosis unless the user explicitly authorizes its removal.

# Large-sample materialization safety

Monthly materialization can contain tens of thousands of entities. Do not place a DataFrame-wide boolean filter (for example, `frame[frame["entity_id"] == ...]`) inside a per-entity, per-horizon, or per-row loop. This produces quadratic or worse work and can run for hours without writing any batch files. Build a keyed index/dictionary once, use a merge/vectorized operation, or use a pre-grouped lookup instead. Any change that builds profile/detail rows at entity scale must retain a regression test proving it does not call the repeated full-frame lookup path.

If a materialization has sustained CPU use while its staging directory remains empty, treat this as a possible pre-write computational-complexity fault. Diagnose the active function before retrying; do not start a second run for the same target while the first is still active.
