from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.services.user_config_service import PermissionError, UserConfigService


def test_admin_effective_config_includes_all_configured_detectors() -> None:
    effective = UserConfigService().effective_detector_config("admin")

    assert "inactive_terminal" in effective["enabled_detectors"]
    assert "price_spread" in effective["enabled_detectors"]
    assert "price_warning" in effective["allowed_categories"]


def test_regional_manager_effective_config_is_limited_to_permissions() -> None:
    effective = UserConfigService().effective_detector_config("js_manager_001")

    assert effective["region_scope"] == ["江苏省"]
    assert "low_price" in effective["enabled_detectors"]
    assert "delivery_refusal" not in effective["enabled_detectors"]


def test_enabling_detector_without_permission_fails(tmp_path) -> None:
    config_path = tmp_path / "users.yaml"
    source_config = Path(__file__).resolve().parents[1] / "config" / "users.yaml"
    shutil.copyfile(source_config, config_path)
    service = UserConfigService(config_path=config_path)

    with pytest.raises(PermissionError):
        service.update_preferences(
            actor_user_id="sales_001",
            target_user_id="sales_001",
            enabled_detectors=["ip_interval", "price_spread"],
        )
