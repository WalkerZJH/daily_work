from __future__ import annotations

from app.schemas.api import DetectorRuntimeConfigPatch
from app.services.detector_config_service import DetectorRuntimeConfigService


def test_runtime_config_patch_thresholds(tmp_path) -> None:
    service = DetectorRuntimeConfigService(tmp_path / "runtime.yaml")

    config, warnings = service.patch_config(
        "delivery_delay_warning",
        DetectorRuntimeConfigPatch(params={"delay_hours_threshold": 72}, updated_by="test"),
    )
    assert warnings == []
    assert config.params["delay_hours_threshold"] == 72

    config, _ = service.patch_config(
        "low_delivery_rate_warning",
        DetectorRuntimeConfigPatch(params={"delivery_rate_threshold": 0.7}, updated_by="test"),
    )
    assert config.params["delivery_rate_threshold"] == 0.7

    config, _ = service.patch_config(
        "price_spread_warning",
        DetectorRuntimeConfigPatch(params={"spread_ratio_threshold": 2.2}, updated_by="test"),
    )
    assert config.params["spread_ratio_threshold"] == 2.2

    config, _ = service.patch_config(
        "purchase_quantity_fluctuation_warning",
        DetectorRuntimeConfigPatch(params={"spike_ratio_threshold": 4.0, "drop_rate_threshold": 0.6}, updated_by="test"),
    )
    assert config.params["spike_ratio_threshold"] == 4.0
    assert config.params["drop_rate_threshold"] == 0.6


def test_ml_dl_first_modes_warn_and_fallback(tmp_path) -> None:
    service = DetectorRuntimeConfigService(tmp_path / "runtime.yaml")

    service.patch_config("price_spread_warning", DetectorRuntimeConfigPatch(mode="ml_first"))
    config, warnings = service.get_config("price_spread_warning")
    assert config.mode == "rule"
    assert "ML_MODEL_NOT_IMPLEMENTED" in warnings

    service.patch_config("purchase_quantity_fluctuation_warning", DetectorRuntimeConfigPatch(mode="dl_first"))
    config, warnings = service.get_config("purchase_quantity_fluctuation_warning")
    assert config.mode == "auto_baseline"
    assert "DL_MODEL_NOT_IMPLEMENTED" in warnings
