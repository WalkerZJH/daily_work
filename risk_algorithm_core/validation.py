"""Validation helpers for risk_algorithm_core inputs and outputs."""

from __future__ import annotations

from pathlib import Path

from risk_result_contracts import validate_result_batch

from .raw_input import read_raw_input_batch


def validate_raw_input_batch(raw_batch_dir: str | Path, schema_mapping_path: str | Path | None = None) -> None:
    read_raw_input_batch(raw_batch_dir, schema_mapping_path)


def validate_monthly_result_batch(batch_dir: str | Path) -> None:
    validate_result_batch(batch_dir)
