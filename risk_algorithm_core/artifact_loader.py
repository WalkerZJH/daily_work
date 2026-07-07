"""Stable model artifact loading for production monthly scoring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import pickle


@dataclass(frozen=True, slots=True)
class ModelArtifactManifest:
    artifact_id: str
    model_family: str
    trained_at: str
    training_data_version: str
    feature_schema_version: str
    required_features: list[str]
    output_score: str
    probability_calibration: str
    caveats: list[str]
    raw: dict[str, Any]


@dataclass(slots=True)
class LoadedModelArtifact:
    manifest: ModelArtifactManifest
    model: Any
    feature_schema: dict[str, Any]
    preprocessing: dict[str, Any]
    calibration: dict[str, Any]
    artifact_dir: Path


def load_current_model_artifact(artifact_dir: str | Path, require_artifact: bool = True) -> LoadedModelArtifact:
    path = Path(artifact_dir)
    manifest_path = path / "artifact_manifest.json"
    if not manifest_path.exists():
        if require_artifact:
            raise FileNotFoundError(f"Model artifact manifest not found: {manifest_path}")
        raise FileNotFoundError(f"Model artifact manifest not found: {manifest_path}")
    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = ModelArtifactManifest(
        artifact_id=str(raw_manifest["artifact_id"]),
        model_family=str(raw_manifest.get("model_family", "unknown")),
        trained_at=str(raw_manifest.get("trained_at", "")),
        training_data_version=str(raw_manifest.get("training_data_version", "")),
        feature_schema_version=str(raw_manifest.get("feature_schema_version", "")),
        required_features=[str(x) for x in raw_manifest.get("required_features", [])],
        output_score=str(raw_manifest.get("output_score", "churn_probability_H")),
        probability_calibration=str(raw_manifest.get("probability_calibration", "raw")),
        caveats=[str(x) for x in raw_manifest.get("caveats", [])],
        raw=raw_manifest,
    )
    feature_schema = _load_optional_json(path / "feature_schema.json")
    preprocessing = _load_optional_json(path / "preprocessing.json")
    calibration = _load_optional_json(path / "calibration.json")
    model = _load_model(path)
    return LoadedModelArtifact(manifest, model, feature_schema, preprocessing, calibration, path)


def validate_feature_schema(feature_columns: list[str], required_features: list[str]) -> None:
    missing = [col for col in required_features if col not in feature_columns]
    if missing:
        raise ValueError(f"Scoring feature frame missing required model features: {missing}")


def _load_model(path: Path) -> Any:
    stub = path / "model_stub.json"
    if stub.exists():
        return json.loads(stub.read_text(encoding="utf-8"))
    pkl = path / "model.pkl"
    if pkl.exists():
        with pkl.open("rb") as fh:
            return pickle.load(fh)
    joblib_file = path / "model.joblib"
    if joblib_file.exists():
        import joblib

        return joblib.load(joblib_file)
    raise FileNotFoundError(f"No supported model file found in {path}")


def _load_optional_json(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}
