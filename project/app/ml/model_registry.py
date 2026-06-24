from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from app.core.config import PROJECT_ROOT
from app.ml.model_contracts import ModelLoadResult
from app.ml.predictors.bgnbd_predictor import BGNBDPredictor
from app.ml.predictors.interval_proxy_predictor import IntervalProxyPredictor
from app.ml.predictors.lgbm_churn_predictor import LGBMChurnPredictor

MODEL_REGISTRY_PATH = PROJECT_ROOT / "configs" / "model_registry.yaml"
MODEL_ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "models"


class ModelRegistry:
    def __init__(
        self,
        registry_path: Path = MODEL_REGISTRY_PATH,
        artifact_root: Path = MODEL_ARTIFACT_ROOT,
    ) -> None:
        self.registry_path = registry_path
        self.artifact_root = artifact_root

    def load_active_backbone(self, features: pd.DataFrame | None = None) -> ModelLoadResult:
        raw = self._read_registry()
        active = raw.get("active_backbone", "palive_interval_proxy")
        return self._load_model(active, raw, features)

    def _load_model(
        self,
        model_name: str,
        registry: dict[str, Any],
        features: pd.DataFrame | None,
    ) -> ModelLoadResult:
        warnings: list[str] = []
        if model_name == "palive_interval_proxy":
            return ModelLoadResult(IntervalProxyPredictor(), warnings)
        if model_name == "palive_bgnbd":
            warnings.append("BGNBD_ACTIVE_MODEL_IS_CANDIDATE_ONLY")
            return ModelLoadResult(BGNBDPredictor(), warnings)
        if model_name == "palive_lgbm":
            model_cfg = (registry.get("models") or {}).get("palive_lgbm", {})
            version = model_cfg.get("active_version")
            if not version:
                return self._fallback(model_cfg, registry, features, "ACTIVE_LGBM_VERSION_NOT_CONFIGURED")
            model_dir = self.artifact_root / "palive_lgbm" / str(version)
            model_path = model_dir / "model.pkl"
            schema_path = model_dir / "feature_schema.json"
            if not model_path.exists() or not schema_path.exists():
                return self._fallback(model_cfg, registry, features, "ACTIVE_LGBM_ARTIFACT_MISSING")
            with schema_path.open("r", encoding="utf-8") as file:
                schema = json.load(file)
            feature_columns = list(schema.get("feature_columns") or [])
            if features is not None:
                missing = [column for column in feature_columns if column not in features.columns]
                if missing:
                    return self._fallback(
                        model_cfg,
                        registry,
                        features,
                        "ACTIVE_LGBM_FEATURE_SCHEMA_MISMATCH",
                    )
            try:
                predictor = LGBMChurnPredictor(
                    model_path=model_path,
                    feature_columns=feature_columns,
                    model_version=str(version),
                )
            except Exception:
                return self._fallback(model_cfg, registry, features, "ACTIVE_LGBM_LOAD_FAILED")
            return ModelLoadResult(predictor, warnings)
        return ModelLoadResult(IntervalProxyPredictor(), [f"UNKNOWN_ACTIVE_MODEL_{model_name}"])

    def _fallback(
        self,
        model_cfg: dict[str, Any],
        registry: dict[str, Any],
        features: pd.DataFrame | None,
        reason: str,
    ) -> ModelLoadResult:
        fallback = model_cfg.get("fallback") or "palive_interval_proxy"
        result = self._load_model(fallback, registry, features)
        return ModelLoadResult(result.predictor, [reason, "MODEL_REGISTRY_FALLBACK_TO_INTERVAL_PROXY", *result.warnings])

    def _read_registry(self) -> dict[str, Any]:
        with self.registry_path.open("r", encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}
        return raw if isinstance(raw, dict) else {}
