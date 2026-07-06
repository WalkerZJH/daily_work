#!/usr/bin/env python
"""Run SQL sampling integrity audit v1."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.sql_sampling_integrity_audit import run_sql_sampling_integrity_audit


DEFAULT_OUTPUT_DIR = ROOT / "reports/sql_sampling_integrity_audit_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SQL sampling integrity audit v1.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--sample-entity-count", type=int, default=500)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--query-timeout", type=int, default=60)
    parser.add_argument("--dry-run", action="store_true", help="Use in-memory fixtures.")
    parser.add_argument("--skip-sql", action="store_true", help="Generate local-only audit without SQL queries.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_sql_sampling_integrity_audit(
        ROOT,
        args.output_dir,
        sample_entity_count=args.sample_entity_count,
        batch_size=args.batch_size,
        query_timeout=args.query_timeout,
        dry_run=args.dry_run,
        skip_sql=args.skip_sql,
    )
    result = outputs["result"]
    print(f"wrote SQL sampling integrity audit outputs to {args.output_dir}")
    print(f"SQL connected: {result.sql_connected}")
    print(f"SQL total row count: {result.sql_total_row_count}")
    print(f"local row count: {result.local_row_count}")
    print(f"sampled entity count: {result.sampled_entity_count}")
    print(f"entity history complete rate: {result.entity_history_complete_rate}")
    print(f"top_n_or_ordered_sample_risk: {result.top_n_or_ordered_sample_risk}")
    print(f"entity_history_incomplete_risk: {result.entity_history_incomplete_risk}")


if __name__ == "__main__":
    main()

