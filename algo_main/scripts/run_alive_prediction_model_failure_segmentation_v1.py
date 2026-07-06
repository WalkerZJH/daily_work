#!/usr/bin/env python
"""Run model failure segmentation and alternative baseline diagnostics."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.model_failure_segmentation import run_model_failure_segmentation


DEFAULT_OUTPUT_DIR = ROOT / "reports/alive_prediction_model_failure_segmentation_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run alive prediction model failure segmentation v1 diagnostics."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Use an in-memory fixture.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_model_failure_segmentation(ROOT, args.output_dir, dry_run=args.dry_run)
    matrix = outputs["segment_metric_matrix"]
    print(f"wrote model failure segmentation outputs to {args.output_dir}")
    print(f"segment rows: {len(matrix)}")
    print(f"good segments: {int(matrix['good_segment'].sum()) if not matrix.empty else 0}")
    print(f"weak segments: {int(matrix['weak_segment'].sum()) if not matrix.empty else 0}")
    print(
        "not predictable segments: "
        f"{int(matrix['not_predictable_segment'].sum()) if not matrix.empty else 0}"
    )


if __name__ == "__main__":
    main()
