#!/usr/bin/env python
"""Run entity_complete_v2 coverage expansion without overwriting v1."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from alg.tasks.die_prediction.entity_complete_v2_coverage_expansion import (  # noqa: E402
    TIER_CONFIGS,
    run_entity_complete_v2_coverage_expansion,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=sorted(TIER_CONFIGS), default="tier_medium")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--estimate-only", action="store_true")
    parser.add_argument("--query-timeout", type=int, default=240)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_entity_complete_v2_coverage_expansion(
        ROOT,
        tier=args.tier,
        dry_run=args.dry_run,
        estimate_only=args.estimate_only,
        query_timeout=args.query_timeout,
    )
    print("status:", result.get("status"))


if __name__ == "__main__":
    main()
