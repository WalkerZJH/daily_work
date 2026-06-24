from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.core.config import PROJECT_ROOT
from app.core.errors import TerminalGuardError
from app.detectors.registry import DETECTOR_META, DetectorMeta, build_default_detector_registry

USER_CONFIG_PATH = PROJECT_ROOT / "config" / "users.yaml"


class PermissionError(TerminalGuardError):
    pass


class UserConfigService:
    def __init__(self, config_path: Path = USER_CONFIG_PATH) -> None:
        self.config_path = config_path

    def detector_catalog(self) -> list[DetectorMeta]:
        return build_default_detector_registry().catalog()

    def get_user_config(self, user_id: str | None) -> dict[str, Any]:
        selected_user_id = user_id or "admin"
        users = self._load_users()
        if selected_user_id not in users:
            raise TerminalGuardError(f"Unknown user_id: {selected_user_id}")
        user = users[selected_user_id]
        effective = self.effective_detector_config(selected_user_id)
        return {
            "user_id": selected_user_id,
            "role": user.get("role"),
            "permissions": user.get("permissions", {}),
            "preference": user.get("preference", {}),
            "effective_detector_config": effective,
        }

    def effective_detector_config(self, user_id: str | None) -> dict[str, Any]:
        selected_user_id = user_id or "admin"
        users = self._load_users()
        if selected_user_id not in users:
            raise TerminalGuardError(f"Unknown user_id: {selected_user_id}")
        user = users[selected_user_id]
        enabled = user.get("preference", {}).get("enabled_detectors") or []
        effective = [detector_id for detector_id in enabled if self._is_detector_allowed(user, detector_id)]
        return {
            "enabled_detectors": effective,
            "allowed_categories": self._allowed_categories(user),
            "region_scope": self.region_scope(selected_user_id),
        }

    def region_scope(self, user_id: str | None) -> list[str]:
        user = self._load_users()[user_id or "admin"]
        permissions = user.get("permissions", {})
        if permissions.get("all_provinces"):
            return []
        return list(permissions.get("region_scope") or [])

    def update_preferences(
        self,
        *,
        actor_user_id: str,
        target_user_id: str,
        enabled_detectors: list[str],
    ) -> dict[str, Any]:
        users = self._load_users()
        if actor_user_id not in users:
            raise PermissionError(f"Unknown actor_user_id: {actor_user_id}")
        if target_user_id not in users:
            raise TerminalGuardError(f"Unknown user_id: {target_user_id}")
        if actor_user_id != target_user_id and users[actor_user_id].get("role") != "admin":
            raise PermissionError("Only admin can update another user's preferences.")
        target = users[target_user_id]
        denied = [
            detector_id
            for detector_id in enabled_detectors
            if detector_id not in DETECTOR_META or not self._is_detector_allowed(target, detector_id)
        ]
        if denied:
            raise PermissionError("Detector preference exceeds permissions: " + ", ".join(denied))
        users[target_user_id].setdefault("preference", {})["enabled_detectors"] = enabled_detectors
        self._write_users(users)
        return self.get_user_config(target_user_id)

    def _allowed_categories(self, user: dict[str, Any]) -> list[str]:
        permissions = user.get("permissions", {})
        if permissions.get("all_categories"):
            return sorted({meta.category for meta in DETECTOR_META.values()})
        return list(permissions.get("allowed_categories") or [])

    def _is_detector_allowed(self, user: dict[str, Any], detector_id: str) -> bool:
        meta = DETECTOR_META.get(detector_id)
        if meta is None:
            return False
        permissions = user.get("permissions", {})
        if permissions.get("all_categories"):
            return True
        return meta.category in set(permissions.get("allowed_categories") or [])

    def _load_users(self) -> dict[str, Any]:
        with self.config_path.open("r", encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}
        users = raw.get("users")
        if not isinstance(users, dict):
            raise TerminalGuardError("User config must contain a users mapping.")
        return users

    def _write_users(self, users: dict[str, Any]) -> None:
        with self.config_path.open("w", encoding="utf-8") as file:
            yaml.safe_dump({"users": users}, file, allow_unicode=True, sort_keys=False)
