#!/usr/bin/env python
"""Build row-level closed-window backtest frames for alive prediction."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.row_level_backtest_frame import build_row_level_backtest_frames


DEFAULT_OUTPUT_DIR = ROOT / "reports/alive_prediction_row_level_backtest_frame_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build alive prediction row-level closed-window backtest frame v1.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Use an in-memory fixture instead of repository artifacts.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = build_row_level_backtest_frames(ROOT, args.output_dir, dry_run=args.dry_run)
    recurring = outputs["recurring"]
    one_shot = outputs["one_shot"]
    recurring_closed = int(recurring["label_window_closed"].astype(bool).sum()) if not recurring.empty else 0
    one_shot_closed = int(one_shot["label_window_closed"].astype(bool).sum()) if not one_shot.empty else 0
    print(f"wrote row-level backtest frames to {args.output_dir}")
    print(f"recurring rows: {len(recurring)}, closed labels: {recurring_closed}")
    print(f"one-shot rows: {len(one_shot)}, closed labels: {one_shot_closed}")


if __name__ == "__main__":
    main()
