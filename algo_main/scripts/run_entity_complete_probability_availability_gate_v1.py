#!/usr/bin/env python
"""Build the static probability availability gate for entity-complete outputs."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from alg.tasks.die_prediction.entity_complete_probability_availability_gate import (  # noqa: E402
    run_probability_availability_gate,
)


DEFAULT_CANDIDATES = ROOT / "data/entity_complete_v2_coverage_expansion/07_candidates/candidate_policy_v2_rows.parquet"
DEFAULT_OUTPUT_DIR = ROOT / "data/entity_complete_v2_coverage_expansion/08_service_gate"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--leakage-not-clean", action="store_true")
    parser.add_argument("--no-selected-subset-caveat", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gate = run_probability_availability_gate(
        args.candidates,
        args.output_dir,
        leakage_clean=not args.leakage_not_clean,
        selected_subset_caveat=not args.no_selected_subset_caveat,
    )
    print("gate rows:", len(gate))
    print("output:", args.output_dir)


if __name__ == "__main__":
    main()
