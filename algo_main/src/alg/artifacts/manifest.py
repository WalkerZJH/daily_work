
"""Manifest schema for model handoff packages."""

from __future__ import annotations

REQUIRED_MANIFEST_FILES = [
    "model.skops",
    "model.joblib",
    "preprocessor.joblib",
    "feature_schema.json",
    "label_definition.yaml",
    "task_config.yaml",
    "train_config.yaml",
    "validation_report.json",
    "metrics.csv",
    "feature_importance.csv",
    "prediction_sample.csv",
    "manifest.json",
    "README.md",
]


def missing_required_files(files: set[str]) -> list[str]:
    """Return required handoff files that are absent from *files*."""

    return [name for name in REQUIRED_MANIFEST_FILES if name not in files]
