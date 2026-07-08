"""Configuration for daily detector result tables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


DEFAULT_DAILY_DETECTOR_CONFIG = Path("configs/risk_algorithm_core/daily_detector_rules.yaml")


@dataclass(frozen=True, slots=True)
class DailyDetectorConfig:
    config_version: str
    effective_from: str
    default_run_scope: str
    detectors: dict[str, dict[str, Any]]
    raw: dict[str, Any]


def load_daily_detector_config(path: str | Path | None = None) -> DailyDetectorConfig:
    config_path = Path(path or DEFAULT_DAILY_DETECTOR_CONFIG)
    data = _load_mapping(config_path)
    return DailyDetectorConfig(
        config_version=str(data.get("config_version") or "daily_detector_rules_v1"),
        effective_from=str(data.get("effective_from") or ""),
        default_run_scope=str(data.get("default_run_scope") or "monthly_high_risk_entities"),
        detectors={str(k): dict(v or {}) for k, v in dict(data.get("detectors", {})).items()},
        raw=data,
    )


def _load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml

        loaded = yaml.safe_load(text)
        return loaded or {}
    except ImportError:
        return _parse_simple_yaml(text)


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    current_child: dict[str, Any] | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0 and ":" in line:
            key, value = line.split(":", 1)
            if value.strip():
                result[key] = _coerce(value.strip())
                current = None
            else:
                result[key] = {}
                current = result[key]
        elif indent == 2 and current is not None and ":" in line:
            key, value = line.split(":", 1)
            if value.strip():
                current[key] = _coerce(value.strip())
                current_child = None
            else:
                current[key] = {}
                current_child = current[key]
        elif indent >= 4 and current_child is not None and ":" in line:
            key, value = line.split(":", 1)
            current_child[key] = _coerce(value.strip())
    return result


def _coerce(value: str) -> Any:
    clean = value.strip().strip('"').strip("'")
    if clean.lower() in {"true", "false"}:
        return clean.lower() == "true"
    if clean.lower() in {"null", "none", ""}:
        return None
    try:
        if "." in clean:
            return float(clean)
        return int(clean)
    except ValueError:
        return clean
