#!/usr/bin/env python
"""Run a fixture monthly risk_algorithm_core check without algorithm internals."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from risk_algorithm_core.monthly_runner import MonthlyRiskRunner  # noqa: E402
from risk_model_core.repositories import ParquetRiskResultRepository  # noqa: E402
from risk_result_contracts import validate_result_batch  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/risk_algorithm_core/monthly_run.example.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--clean-output", action="store_true")
    args = parser.parse_args()

    out = REPO_ROOT / ".tmp" / "risk_algorithm_core_batches"
    if args.clean_output and out.exists():
        shutil.rmtree(out)

    summary = MonthlyRiskRunner.from_config_file(REPO_ROOT / args.config).run(use_rule_baseline=bool(args.dry_run))
    batch_dir = REPO_ROOT / summary["batch_dir"]
    validate_result_batch(batch_dir)
    repo = ParquetRiskResultRepository(batch_dir)
    entities = repo.list_risk_entities()
    cards = repo.load_table("risk_cards")

    print("monthly_run_check: ok")
    print("report_month:", summary["report_month"])
    print("cutoff_date:", summary["cutoff_date"])
    print("entity_rows:", summary["entity_rows"])
    print("feature_rows:", summary["feature_rows"])
    print("score_rows:", summary["score_rows"])
    print("selected_candidate_rows:", summary["selected_candidate_rows"])
    print("risk_entities:", len(entities))
    print("risk_cards:", len(cards))
    print("batch_dir:", batch_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
