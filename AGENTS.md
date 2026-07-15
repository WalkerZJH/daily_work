# Long-running batch safety

Before starting or restarting a monthly result-batch materialization, inspect the target `report_month` and `run_id` for an existing formal directory, a hidden `.staging-*` directory, and a live matching process. If a matching process or staging directory exists, monitor it and do not start another materialization unless the user explicitly authorizes a restart after the prior process has ended or been diagnosed as failed. Never run concurrent materializations for the same target batch.

Do not delete, overwrite, or reuse an existing formal batch directory. A retry must use a new versioned `run_id` and preserve the prior staging directory for diagnosis unless the user explicitly authorizes its removal.
