from __future__ import annotations

from datetime import date

from app.core.config import load_config
from app.detectors.cycle_deviation import CycleDeviationDetector
from app.detectors.inactive_terminal import InactiveTerminalDetector
from app.detectors.new_terminal import NewTerminalDetector
from app.detectors.substitution_risk import SubstitutionRiskDetector
from app.features.snapshot import FeatureSnapshot


def _snapshot(features: dict[str, object], warnings: list[str] | None = None) -> FeatureSnapshot:
    return FeatureSnapshot(
        unit_id="ORG_X|product_line|PL_X",
        org_code="ORG_X",
        analysis_grain="product_line",
        target_code="PL_X",
        as_of_date=date(2025, 12, 31),
        features=features,
        warnings=warnings or [],
    )


def test_detector_missing_required_features_does_not_crash() -> None:
    result = NewTerminalDetector().detect([_snapshot({"has_recent_order": True})], load_config())[0]

    assert result.hit is False
    assert result.confidence == 0
    assert result.reason_code == "MISSING_REQUIRED_FEATURES"
    assert "MISSING_REQUIRED_FEATURES" in result.warnings


def test_inactive_terminal_uses_typical_refill_days_when_available() -> None:
    result = InactiveTerminalDetector().detect(
        [
            _snapshot(
                {
                    "inactive_days": 120,
                    "historical_median_ipi": 1000,
                    "adi": 1000,
                    "typical_refill_days": 30,
                    "demand_shape": "smooth",
                }
            )
        ],
        load_config(),
    )[0]

    assert result.hit is True
    assert result.metrics["reference_source"] == "typical_refill_days"


def test_substitution_risk_low_confidence_warns_without_competitor_claim() -> None:
    result = SubstitutionRiskDetector().detect(
        [
            _snapshot(
                {
                    "own_recent_qty": 10,
                    "own_baseline_qty": 100,
                    "same_group_recent_qty": 100,
                    "same_group_baseline_qty": 100,
                    "substitute_qty_delta": 0,
                    "substitution_feature_confidence": 0.1,
                },
                warnings=["LIMITED_TO_OWN_PRODUCTS"],
            )
        ],
        load_config(),
    )[0]

    assert result.hit is False
    assert result.reason_code == "INSUFFICIENT_MARKET_DATA"
    assert "LIMITED_TO_OWN_PRODUCTS" in result.warnings


def test_cycle_deviation_missing_cycle_prior_does_not_crash() -> None:
    result = CycleDeviationDetector().detect(
        [_snapshot({"inactive_days": 120})],
        load_config(),
    )[0]

    assert result.hit is False
    assert result.reason_code == "MISSING_REQUIRED_FEATURES"
    assert "MISSING_TREATMENT_CYCLE_PRIOR" in result.warnings
