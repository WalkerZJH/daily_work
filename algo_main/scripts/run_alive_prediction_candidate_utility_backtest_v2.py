#!/usr/bin/env python
"""Run candidate-level alive prediction utility backtest v2."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.utility_backtest_v2 import run_candidate_utility_backtest_v2


DEFAULT_OUTPUT_DIR = ROOT / "reports/alive_prediction_candidate_utility_backtest_v2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run candidate-level alive prediction utility backtest v2.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Use a small in-memory fixture.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_candidate_utility_backtest_v2(ROOT, args.output_dir, dry_run=args.dry_run)
    recurring_closed = int(
        outputs["recurring"]["label_window_closed"].astype(bool).sum()
    ) if not outputs["recurring"].empty and "label_window_closed" in outputs["recurring"].columns else 0
    one_shot_closed = int(
        outputs["one_shot"]["label_window_closed"].astype(bool).sum()
    ) if not outputs["one_shot"].empty and "label_window_closed" in outputs["one_shot"].columns else 0
    print(f"wrote candidate utility backtest v2 outputs to {args.output_dir}")
    print(f"recurring closed rows: {recurring_closed}")
    print(f"one-shot closed rows: {one_shot_closed}")
    print(f"proof cases: {len(outputs['proof'])}")


if __name__ == "__main__":
    main()
