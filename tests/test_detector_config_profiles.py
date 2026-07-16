from __future__ import annotations

import pandas as pd
import pytest

from risk_algorithm_core.detector_config import load_daily_detector_config
from risk_algorithm_core.detector_config_profiles import (
    build_manufacturer_config_profiles,
    build_run_config_snapshot,
    resolve_detector_config_profiles,
)


def test_profiles_are_explicit_per_manufacturer_and_never_global_fallback() -> None:
    config = load_daily_detector_config()
    profiles = build_manufacturer_config_profiles(
        ["m1", "m2"], config, detector_ids=["purchase_interval_ipi"], created_at="2026-07-16T00:00:00+00:00"
    )
    assert len(profiles) == 2
    assert set(profiles["manufacturer_code"]) == {"m1", "m2"}
    assert set(profiles["parameter_scope"]) == {"manufacturer_specific"}
    assert set(profiles["generation_method"]) == {"copied_template_unapproved"}
    assert set(profiles["business_approval_status"]) == {"pending"}

    resolved, missing = resolve_detector_config_profiles(
        profiles,
        detector_id="purchase_interval_ipi",
        manufacturer_codes=["m1", "m3"],
        observation_date="2026-07-16",
    )
    assert resolved["manufacturer_code"].tolist() == ["m1"]
    assert missing == ["m3"]


def test_duplicate_effective_profile_is_rejected() -> None:
    config = load_daily_detector_config()
    profiles = build_manufacturer_config_profiles(["m1"], config, detector_ids=["purchase_interval_ipi"])
    duplicate = pd.concat([profiles, profiles.assign(config_id="another")], ignore_index=True)
    with pytest.raises(ValueError, match="Multiple effective"):
        resolve_detector_config_profiles(
            duplicate,
            detector_id="purchase_interval_ipi",
            manufacturer_codes=["m1"],
            observation_date="2026-07-16",
        )


def test_run_snapshot_stores_hash_not_payload() -> None:
    config = load_daily_detector_config()
    profiles = build_manufacturer_config_profiles(["m1"], config, detector_ids=["purchase_interval_ipi"])
    snapshot = build_run_config_snapshot(profiles, run_id="run-1", observation_date="2026-07-16")
    assert snapshot.iloc[0]["config_id"] == profiles.iloc[0]["config_id"]
    assert snapshot.iloc[0]["config_hash"] == profiles.iloc[0]["config_hash"]
    assert "config_payload" not in snapshot.columns
