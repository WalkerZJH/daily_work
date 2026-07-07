"""Command line interface for monthly production risk runs."""

from __future__ import annotations

import argparse
from pathlib import Path

from .monthly_runner import MonthlyRiskRunner
from .validation import raw_input_validation_report, validate_raw_input_batch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="risk_algorithm_core")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run")
    run_p.add_argument("--config", required=True)

    dry_p = sub.add_parser("dry-run")
    dry_p.add_argument("--config", required=True)
    dry_p.add_argument("--use-rule-baseline", action="store_true", default=True)

    val_p = sub.add_parser("validate-raw")
    val_p.add_argument("--raw-batch", required=True)
    val_p.add_argument("--schema-mapping")
    val_p.add_argument("--output-report")

    args = parser.parse_args(argv)
    if args.command == "validate-raw":
        validate_raw_input_batch(args.raw_batch, args.schema_mapping)
        if args.output_report:
            raw_input_validation_report(args.raw_batch, args.schema_mapping).to_csv(args.output_report, index=False)
        print("raw_input_validation: ok")
        return 0
    if args.command == "run":
        summary = MonthlyRiskRunner.from_config_file(args.config).run(use_rule_baseline=False)
        print("monthly_run: ok")
        print("batch_dir:", summary["batch_dir"])
        return 0
    if args.command == "dry-run":
        summary = MonthlyRiskRunner.from_config_file(args.config).run(use_rule_baseline=True)
        print("monthly_dry_run: ok")
        print("batch_dir:", summary["batch_dir"])
        return 0
    raise ValueError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
