#!/usr/bin/env python
"""Create stale artifact manifest and archive old derived data for entity_complete_v1."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.entity_complete_rebuild import run_reset_cleanup


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset old derived artifacts before entity_complete_v1 rebuild.")
    parser.add_argument("--plan-only", action="store_true", help="Write manifest/plan without moving files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_reset_cleanup(ROOT, execute=not args.plan_only)
    print(f"stale manifest rows: {len(outputs['manifest'])}")
    print(f"archived files: {len(outputs['archived'])}")


if __name__ == "__main__":
    main()

