#!/usr/bin/env python
"""Run full-universe interval backtest v1 for alive prediction."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.full_universe_interval_backtest import run_full_universe_interval_backtest


DEFAULT_OUTPUT_DIR = ROOT / "reports/alive_prediction_full_universe_interval_backtest_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run alive prediction full-universe interval backtest v1.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Use an in-memory fixture.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_full_universe_interval_backtest(ROOT, args.output_dir, dry_run=args.dry_run)
    frame = outputs["frame"]
    coverage = outputs["coverage"]
    closed_rows = int(frame["label_window_closed"].astype(bool).sum()) if not frame.empty else 0
    cov = coverage[(coverage["horizon"].eq("overall")) & (coverage["cutoff_month"].eq("all_2024"))]
    candidate_recall = cov["candidate_die_recall"].iloc[0] if not cov.empty else float("nan")
    print(f"wrote full-universe interval backtest outputs to {args.output_dir}")
    print(f"full-universe frame rows: {len(frame)}")
    print(f"closed label rows: {closed_rows}")
    print(f"candidate die recall: {candidate_recall:.4f}" if candidate_recall == candidate_recall else "candidate die recall: nan")
    print(f"logistic score available: {outputs['score_status'].get('available', False)}")


if __name__ == "__main__":
    main()
