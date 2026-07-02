#!/usr/bin/env python
"""Run alive prediction utility backtest v1.

This script reads existing report artifacts only. It does not train models,
rerun M1-M7, modify upstream outputs, call LLMs, or generate frontend assets.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.utility_backtest import run_utility_backtest


DEFAULT_OUTPUT_DIR = ROOT / "reports/alive_prediction_utility_backtest_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run read-only alive prediction utility backtest v1.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Use a small in-memory fixture instead of repository reports.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_utility_backtest(ROOT, args.output_dir, dry_run=args.dry_run)
    print(f"wrote utility backtest outputs to {args.output_dir}")
    print(f"universe rows: {int(outputs['universe']['row_count'].sum()) if not outputs['universe'].empty else 0}")
    print(f"proof cases: {len(outputs['proof_cases'])}")


if __name__ == "__main__":
    main()
