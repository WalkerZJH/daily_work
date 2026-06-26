#!/usr/bin/env python
"""Run rolling cutoff temporal backtests."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/task_registry.yaml", help="Path to YAML config.")
    parser.add_argument("--input", default=None, help="Optional input path.")
    parser.add_argument("--output", default=None, help="Optional output path.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    print(f"TODO: {parser.description.strip()}")
    print(f"config={args.config} input={args.input} output={args.output}")


if __name__ == "__main__":
    main()
