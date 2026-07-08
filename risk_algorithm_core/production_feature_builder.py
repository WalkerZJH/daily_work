"""Align runtime raw-derived features to a frozen production artifact schema."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .artifact_loader import LoadedModelArtifact


@dataclass(frozen=True, slots=True)
class ProductionFeatureBuildResult:
    model_feature_frame: pd.DataFrame
    parity_report: pd.DataFrame


def build_model_feature_frame(features: pd.DataFrame, artifact: LoadedModelArtifact) -> ProductionFeatureBuildResult:
    schema = artifact.feature_schema or {}
    required = artifact.manifest.required_features
    feature_order = [str(x) for x in schema.get("feature_order", required)]
    if feature_order != required:
        required = feature_order

    work = features.copy()
    default_values = dict(schema.get("default_fill_values", {}))
    dtype_policy = dict(schema.get("dtype_policy", {}))
    rows: list[dict[str, Any]] = []

    for feature in required:
        if feature not in work.columns:
            if feature in default_values:
                work[feature] = default_values[feature]
                status = "generated_from_schema_default"
            else:
                raise ValueError(f"Production feature builder cannot produce required feature: {feature}")
        else:
            status = "available_from_raw_feature_engineering"
        before_missing = int(work[feature].isna().sum())
        fill_existing_missing = status == "generated_from_schema_default"
        work[feature] = _coerce_feature(
            work[feature],
            dtype_policy.get(feature),
            default_values.get(feature),
            fill_missing=fill_existing_missing,
        )
        after_missing = int(work[feature].isna().sum())
        rows.append(
            {
                "required_feature": feature,
                "production_dtype": str(work[feature].dtype),
                "missing_before": before_missing,
                "missing_after": after_missing,
                "production_imputation": "schema_default" if status == "generated_from_schema_default" else "runtime_generated",
                "implemented_in_risk_algorithm_core": True,
                "parity_status": status,
                "blocker_reason": "",
            }
        )

    passthrough = [
        "entity_id",
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "drug_group_source",
        "cutoff_month",
        "horizon",
    ]
    meta_cols = [c for c in passthrough if c in features.columns and c not in required]
    model_frame = pd.concat([features[meta_cols].reset_index(drop=True), work[required].reset_index(drop=True)], axis=1)
    return ProductionFeatureBuildResult(model_frame, pd.DataFrame(rows))


def _coerce_feature(series: pd.Series, dtype_name: str | None, default_value: Any, *, fill_missing: bool) -> pd.Series:
    if dtype_name in {"float", "float64", "number", "numeric"}:
        out = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
        if fill_missing and default_value is not None:
            out = out.fillna(float(default_value))
        return out
    if dtype_name in {"int", "int64"}:
        out = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
        if fill_missing and default_value is not None:
            out = out.fillna(int(default_value))
        return out.astype("int64", errors="ignore")
    if dtype_name in {"bool", "boolean"}:
        if fill_missing:
            return series.fillna(bool(default_value) if default_value is not None else False).astype(bool)
        return series.astype("boolean")
    out = series.astype("string")
    if fill_missing:
        out = out.fillna(str(default_value) if default_value is not None else "__missing__")
    return out.astype(object)
