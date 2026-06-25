from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.core.config import PROJECT_ROOT
from app.detectors.registry import DETECTOR_META
from app.schemas.api import DetectorRuntimeConfig, DetectorRuntimeConfigPatch


DEFAULT_RUNTIME_PARAMS: dict[str, dict[str, Any]] = {
    "low_price_warning": {
        "warning_price": None,
        "auto_baseline_method": "mean_factor",
        "auto_baseline_factor": 0.9,
        "auto_baseline_quantile": 0.1,
    },
    "price_spread_warning": {"spread_ratio_threshold": 1.8},
    "delivery_delay_warning": {"delay_hours_threshold": 48},
    "low_delivery_rate_warning": {"delivery_rate_threshold": 0.8, "province_thresholds": {}},
    "delivery_rejection_warning": {
        "status_keywords": ["拒绝", "退货", "无法配送", "缺货", "驳回", "拒收", "撤单"]
    },
    "terminal_lost_warning": {"inactive_days_multiplier": 1.5, "min_history_orders": 2},
    "new_terminal_warning": {"new_terminal_min_qty": 1, "comeback_days": 180},
    "purchase_quantity_fluctuation_warning": {"spike_ratio_threshold": 3.0, "drop_rate_threshold": 0.5},
    "purchase_frequency_fluctuation_warning": {"spike_ratio_threshold": 2.0, "drop_rate_threshold": 0.5},
}

DEFAULT_RUNTIME_MODES: dict[str, str] = {
    "low_price_warning": "rule",
    "price_spread_warning": "rule",
    "delivery_delay_warning": "rule",
    "low_delivery_rate_warning": "rule",
    "delivery_rejection_warning": "rule",
    "terminal_lost_warning": "auto_baseline",
    "new_terminal_warning": "rule",
    "purchase_quantity_fluctuation_warning": "auto_baseline",
    "purchase_frequency_fluctuation_warning": "auto_baseline",
}


class DetectorRuntimeConfigService:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or PROJECT_ROOT / "configs" / "detector_runtime.yaml"

    def list_configs(self) -> list[DetectorRuntimeConfig]:
        raw = self._load_raw()
        return [self.get_config(detector_id, raw=raw)[0] for detector_id in DETECTOR_META]

    def get_config(self, detector_id: str, raw: dict[str, Any] | None = None) -> tuple[DetectorRuntimeConfig, list[str]]:
        if detector_id not in DETECTOR_META:
            raise KeyError(detector_id)
        raw = raw if raw is not None else self._load_raw()
        spec = DETECTOR_META[detector_id]
        item = raw.get(detector_id) or {}
        params = dict(DEFAULT_RUNTIME_PARAMS.get(detector_id, {}))
        params.update(item.get("params") or {})
        mode = item.get("mode") or DEFAULT_RUNTIME_MODES.get(detector_id, "rule")
        warnings: list[str] = []
        if mode == "ml_first":
            warnings.append("ML_MODEL_NOT_IMPLEMENTED")
            mode = "auto_baseline" if DEFAULT_RUNTIME_MODES.get(detector_id) == "auto_baseline" else "rule"
        elif mode == "dl_first":
            warnings.append("DL_MODEL_NOT_IMPLEMENTED")
            mode = "auto_baseline" if DEFAULT_RUNTIME_MODES.get(detector_id) == "auto_baseline" else "rule"
        config = DetectorRuntimeConfig(
            detector_id=detector_id,
            category=spec.category,
            enabled=bool(item.get("enabled", spec.enabled_by_default)),
            mode=mode,
            params=params,
            scope_type=item.get("scope_type", "global"),
            scope_value=item.get("scope_value"),
            updated_by=item.get("updated_by"),
            updated_at=item.get("updated_at"),
        )
        return config, warnings

    def patch_config(self, detector_id: str, patch: DetectorRuntimeConfigPatch) -> tuple[DetectorRuntimeConfig, list[str]]:
        if detector_id not in DETECTOR_META:
            raise KeyError(detector_id)
        raw = self._load_raw()
        current = dict(raw.get(detector_id) or {})
        if patch.enabled is not None:
            current["enabled"] = patch.enabled
        if patch.mode is not None:
            current["mode"] = patch.mode
        if patch.params is not None:
            params = dict(current.get("params") or {})
            params.update(patch.params)
            current["params"] = params
        if patch.scope_type is not None:
            current["scope_type"] = patch.scope_type
        if patch.scope_value is not None:
            current["scope_value"] = patch.scope_value
        current["updated_by"] = patch.updated_by or "local"
        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        raw[detector_id] = current
        self._write_raw(raw)
        return self.get_config(detector_id, raw=raw)

    def warning_summary_for(self, detector_ids: list[str]) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for detector_id in detector_ids:
            _, warnings = self.get_config(detector_id)
            counter.update(warnings)
        return dict(counter)

    def _load_raw(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._legacy_thresholds()
        with self.path.open("r", encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}
        return raw if isinstance(raw, dict) else {}

    def _write_raw(self, raw: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            yaml.safe_dump(raw, file, allow_unicode=True, sort_keys=True)

    @staticmethod
    def _legacy_thresholds() -> dict[str, Any]:
        path = PROJECT_ROOT / "configs" / "detector_thresholds.yaml"
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as file:
            legacy = yaml.safe_load(file) or {}
        raw: dict[str, Any] = {}
        for detector_id, params in legacy.items():
            if not isinstance(params, dict):
                continue
            translated = dict(params)
            if detector_id == "low_delivery_rate_warning":
                translated["delivery_rate_threshold"] = translated.pop("default_threshold", translated.get("delivery_rate_threshold", 0.8))
            if detector_id == "delivery_delay_warning":
                translated["delay_hours_threshold"] = translated.pop("threshold_hours", translated.get("delay_hours_threshold", 48))
            if detector_id == "terminal_lost_warning":
                translated["inactive_days_multiplier"] = translated.pop("cycle_multiplier", translated.get("inactive_days_multiplier", 1.5))
            if detector_id == "new_terminal_warning":
                translated["new_terminal_min_qty"] = translated.pop("min_purchase_qty", translated.get("new_terminal_min_qty", 1))
            if detector_id in {"purchase_quantity_fluctuation_warning", "purchase_frequency_fluctuation_warning"}:
                translated["drop_rate_threshold"] = translated.pop("drop_ratio_threshold", translated.get("drop_rate_threshold", 0.5))
            raw[detector_id] = {
                "enabled": DETECTOR_META.get(detector_id).enabled_by_default if detector_id in DETECTOR_META else True,
                "mode": DEFAULT_RUNTIME_MODES.get(detector_id, "rule"),
                "params": translated,
                "scope_type": "global",
                "scope_value": None,
            }
        return raw
