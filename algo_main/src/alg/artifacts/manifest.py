
"""Manifest helpers.

This module still exposes the model handoff manifest checks used by earlier
tests, and also provides a lightweight artifact index for data-layer artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


def read_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return {"artifacts": []}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def write_manifest(path: str | Path, manifest: dict[str, Any]) -> None:
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def update_manifest(path: str | Path, artifact_record: dict[str, Any]) -> dict[str, Any]:
    manifest = read_manifest(path)
    records = [
        record
        for record in manifest.get("artifacts", [])
        if record.get("artifact_name") != artifact_record.get("artifact_name")
        or record.get("path") != artifact_record.get("path")
    ]
    records.append(artifact_record)
    manifest["artifacts"] = records
    write_manifest(path, manifest)
    return manifest
