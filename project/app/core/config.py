from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from app.schemas.config import AppConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.yaml"


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_raw_config(config_path: str | Path | None = None) -> dict[str, Any]:
    selected_path = Path(config_path or os.getenv("APP_CONFIG_PATH", DEFAULT_CONFIG_PATH))
    if not selected_path.is_absolute():
        selected_path = PROJECT_ROOT / selected_path
    with selected_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a mapping: {selected_path}")
    return raw


def load_config(
    config_path: str | Path | None = None,
    patch: dict[str, Any] | None = None,
) -> AppConfig:
    raw = load_raw_config(config_path)
    if patch:
        raw = deep_merge(raw, patch)
    return AppConfig.model_validate(raw)
