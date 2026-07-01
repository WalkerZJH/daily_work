#!/usr/bin/env python
"""Dry-run alive prediction repository cleanup audit."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from alg.utils.repo_cleanup_audit import apply_archive, write_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Only write audit reports. This is the default.")
    mode.add_argument("--apply", action="store_true", help="Move reviewed archive candidates to _archive/. Never deletes.")
    parser.add_argument("--confirm", action="store_true", help="Required with --apply.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = ROOT / "reports/repo_cleanup_alive_prediction"
    outputs = write_report(ROOT, output_dir, dry_run=not args.apply)
    if args.apply:
        apply_archive(ROOT, output_dir, confirm=args.confirm)
    print(outputs["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
