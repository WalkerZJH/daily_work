#!/usr/bin/env python
"""Generate alive prediction M1-M7 stage-end algorithm risk review."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.stage_end_audit import run_stage_end_audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Run against a small synthetic fixture.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory. Defaults to reports/alive_prediction_stage_end_audit_v1.",
    )
    parser.add_argument(
        "--fixture-root",
        type=Path,
        default=None,
        help="Optional dry-run fixture root for tests.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = ROOT
    if args.dry_run:
        project_root = args.fixture_root or ROOT / "reports/alive_prediction_stage_end_audit_v1/_dry_run_fixture"
    result = run_stage_end_audit(project_root=project_root, output_dir=args.output_dir, dry_run=args.dry_run)
    print(f"stage_freeze_decision={result['stage_freeze_decision']}")
    print(f"required_fix_count={result['required_fix_count']}")
    print(f"output_dir={result['output_dir']}")


if __name__ == "__main__":
    main()
