#!/usr/bin/env python
"""Run entity_complete_v1 SQL extraction."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.entity_complete_rebuild import run_entity_complete_sql_extract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run manufacturer/entity-complete SQL extract v1.")
    parser.add_argument("--max-manufacturers", type=int, default=4)
    parser.add_argument("--max-entities", type=int, default=1500)
    parser.add_argument("--max-hospital-drug-pairs", type=int, default=3000)
    parser.add_argument("--query-timeout", type=int, default=120)
    parser.add_argument("--estimate-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_entity_complete_sql_extract(
        ROOT,
        max_manufacturers=args.max_manufacturers,
        max_entities=args.max_entities,
        max_hospital_drug_pairs=args.max_hospital_drug_pairs,
        dry_run=args.dry_run,
        estimate_only=args.estimate_only,
        refresh=args.refresh,
        query_timeout=args.query_timeout,
    )
    print("selected manufacturers:", ",".join(outputs["selected_manufacturers"]["manufacturer_code"].astype(str)))
    print("selected entity count:", len(outputs["selected_entities"]))
    print("selected hospital-drug pair count:", len(outputs["selected_hospital_drug_pairs"]))
    print("manufacturer extracted rows:", outputs["manufacturer_rows"])
    print("entity extracted rows:", outputs["entity_rows"])
    print("hospital-drug choice-set extracted rows:", outputs["hospital_drug_rows"])
    print(f"SQL runtime seconds: {outputs['runtime']:.2f}")


if __name__ == "__main__":
    main()
