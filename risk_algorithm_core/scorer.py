"""Risk scoring interfaces for monthly production runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math

import numpy as np
import pandas as pd

from .artifact_loader import LoadedModelArtifact, validate_feature_schema


class BaseRiskScorer:
    def score(self, feature_frame: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError


@dataclass(slots=True)
class ArtifactRiskScorer(BaseRiskScorer):
    artifact: LoadedModelArtifact

    def score(self, feature_frame: pd.DataFrame) -> pd.DataFrame:
        required = self.artifact.manifest.required_features
        validate_feature_schema(list(feature_frame.columns), required)
        if isinstance(self.artifact.model, dict) and self.artifact.model.get("type") == "linear_stub":
            probs = _linear_stub_predict(feature_frame, self.artifact.model)
        elif isinstance(self.artifact.model, dict) and self.artifact.model.get("type") == "per_horizon_pipeline":
            probs = _per_horizon_pipeline_predict(feature_frame, self.artifact.model, required)
        elif hasattr(self.artifact.model, "predict_proba"):
            probs = self.artifact.model.predict_proba(feature_frame[required])[:, 1]
        else:
            raise TypeError("Unsupported model artifact type for production scoring.")
        probs = np.asarray(probs, dtype=float)
        if np.isnan(probs).any() or (probs < 0).any() or (probs > 1).any():
            raise ValueError("ArtifactRiskScorer produced invalid probability values.")
        return _score_frame(
            feature_frame,
            probs,
            "artifact",
            self.artifact.manifest.artifact_id,
            feature_schema_version=self.artifact.manifest.feature_schema_version,
        )


@dataclass(slots=True)
class RuleBaselineScorer(BaseRiskScorer):
    artifact_id: str = "dry_run_rule_baseline"
    allow_formal_batch: bool = False

    def score(self, feature_frame: pd.DataFrame) -> pd.DataFrame:
        if self.allow_formal_batch:
            raise ValueError("RuleBaselineScorer cannot be marked as formal production scorer.")
        raw = (
            0.35 * feature_frame["months_since_last_purchase"].fillna(0).clip(0, 24) / 24
            + 0.25 * feature_frame["current_interval_over_median"].fillna(0).clip(0, 4) / 4
            + 0.20 * (1 - feature_frame["frequency_ratio"].fillna(1).clip(0, 1))
            + 0.20 * (1 - feature_frame["quantity_ratio"].fillna(1).clip(0, 1))
        )
        probs = raw.clip(0.01, 0.99)
        return _score_frame(feature_frame, probs, "dry_run_rule_baseline", self.artifact_id, feature_schema_version="dry_run_rule_baseline")


def _linear_stub_predict(df: pd.DataFrame, model: dict[str, Any]) -> np.ndarray:
    intercept = float(model.get("intercept", 0.0))
    weights = {str(k): float(v) for k, v in model.get("weights", {}).items()}
    z = np.full(len(df), intercept, dtype=float)
    for feature, weight in weights.items():
        if feature in df:
            z += df[feature].fillna(0).astype(float).to_numpy() * weight
    return np.array([1.0 / (1.0 + math.exp(-float(x))) for x in z])


def _per_horizon_pipeline_predict(df: pd.DataFrame, model: dict[str, Any], required: list[str]) -> np.ndarray:
    work = df.reset_index(drop=True)
    out = np.full(len(work), np.nan, dtype=float)
    horizon_models = model.get("horizon_models", {})
    for horizon, part in work.groupby("horizon", dropna=False):
        key = str(horizon)
        pipeline = horizon_models.get(key)
        if pipeline is None:
            raise ValueError(f"Model artifact missing fitted pipeline for horizon {key}.")
        scores = pipeline.predict_proba(part[required])[:, 1]
        out[part.index.to_numpy()] = np.asarray(scores, dtype=float)
    return out


def _score_frame(features: pd.DataFrame, probs: Any, source: str, artifact_id: str, *, feature_schema_version: str) -> pd.DataFrame:
    out = features[
        [
            "entity_id",
            "manufacturer_code",
            "hospital_code",
            "drug_group",
            "drug_group_source",
            "cutoff_month",
            "horizon",
        ]
    ].copy()
    out["candidate_id"] = out["entity_id"].astype(str) + "|" + out["horizon"].astype(str)
    out["churn_probability_H"] = np.asarray(probs, dtype=float).clip(0.0, 1.0)
    out["risk_score"] = out["churn_probability_H"]
    out["score_source"] = source
    out["artifact_id"] = artifact_id
    out["feature_schema_version"] = feature_schema_version
    out["score_caveat"] = "dry_run_only" if source == "dry_run_rule_baseline" else ""
    return out
