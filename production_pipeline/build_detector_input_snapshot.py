from __future__ import annotations

import argparse

from risk_algorithm_core.raw_input import read_raw_input_batch
from risk_result_contracts import write_production_parquet

from .common import require_batch_dir
from .detector_input_snapshot import build_detector_input_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the fact-only input for one daily detector run.")
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--raw-batch-dir", required=True)
    parser.add_argument("--observation-date", required=True)
    parser.add_argument("--schema-mapping-path")
    args = parser.parse_args(argv)
    batch_dir = require_batch_dir(args.batch_dir)
    raw = read_raw_input_batch(args.raw_batch_dir, args.schema_mapping_path)
    snapshot = build_detector_input_snapshot(raw.tables["orders"], args.observation_date)
    write_production_parquet(snapshot, batch_dir / "detector_input_snapshot.parquet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
