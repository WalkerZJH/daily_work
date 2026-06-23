from __future__ import annotations

from app.core.config import load_config
from app.schemas.config import AppConfig


def get_app_config() -> AppConfig:
    return load_config()
