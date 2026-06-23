from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WindowConfig(StrictConfigModel):
    recent_days: int = Field(default=90, gt=0)
    baseline_days: int = Field(default=365, gt=0)


class DemandShapeConfig(StrictConfigModel):
    adi_threshold: float = Field(default=1.32, gt=0)
    cv2_threshold: float = Field(default=0.49, ge=0)
    min_nonzero_periods: int = Field(default=3, ge=2)


class IPIntervalConfig(StrictConfigModel):
    enabled: bool = True
    family: str = "terminal_activity"
    z_hit: float = Field(default=1.5, gt=0)
    z_full: float = Field(default=3.5, gt=0)
    min_orders: int = Field(default=6, ge=2)


class FrequencyDropConfig(StrictConfigModel):
    enabled: bool = True
    family: str = "terminal_activity"
    drop_threshold: float = Field(default=0.6, gt=0, lt=1)
    min_base_monthly_orders: float = Field(default=1, ge=0)


class SkuShrinkConfig(StrictConfigModel):
    enabled: bool = True
    family: str = "assortment_change"
    shrink_threshold: float = Field(default=0.34, gt=0, lt=1)
    min_base_sku_count: int = Field(default=2, ge=1)


class InactiveTerminalConfig(StrictConfigModel):
    enabled: bool = True
    family: str = "terminal_activity"
    inactive_multiplier: float = Field(default=3.0, gt=0)
    min_inactive_days: int = Field(default=90, ge=1)


class NewTerminalConfig(StrictConfigModel):
    enabled: bool = True
    family: str = "terminal_expansion"


class SubstitutionRiskConfig(StrictConfigModel):
    enabled: bool = True
    family: str = "substitution"
    own_drop_threshold: float = Field(default=0.6, gt=0, lt=1)
    same_group_stable_threshold: float = Field(default=0.9, gt=0)


class CycleDeviationConfig(StrictConfigModel):
    enabled: bool = True
    family: str = "cycle_prior"
    deviation_multiplier: float = Field(default=2.0, gt=0)
    min_cycle_confidence: float = Field(default=0.3, ge=0, le=1)


class DetectorConfig(StrictConfigModel):
    ip_interval: IPIntervalConfig
    frequency_drop: FrequencyDropConfig
    sku_shrink: SkuShrinkConfig
    inactive_terminal: InactiveTerminalConfig
    new_terminal: NewTerminalConfig
    substitution_risk: SubstitutionRiskConfig
    cycle_deviation: CycleDeviationConfig


class TemporalWindowPreprocessorConfig(StrictConfigModel):
    enabled: bool = True
    recent_days: int = Field(default=90, gt=0)
    baseline_days: int = Field(default=365, gt=0)


class UnitBuilderPreprocessorConfig(StrictConfigModel):
    enabled: bool = True
    grains: list[str] = Field(default_factory=lambda: ["product_line", "sku"])


class DemandShapePreprocessorConfig(StrictConfigModel):
    enabled: bool = True
    adi_threshold: float = Field(default=1.32, gt=0)
    cv2_threshold: float = Field(default=0.49, ge=0)
    min_nonzero_periods: int = Field(default=3, ge=2)


class DrugGroupingPreprocessorConfig(StrictConfigModel):
    enabled: bool = True
    allow_missing_mapping: bool = True


class TreatmentCyclePreprocessorConfig(StrictConfigModel):
    enabled: bool = True
    allow_missing_cycle_prior: bool = True


class SubstitutionFeaturesPreprocessorConfig(StrictConfigModel):
    enabled: bool = True
    allow_own_product_only: bool = True


class CohortContextPreprocessorConfig(StrictConfigModel):
    enabled: bool = False


class SeasonalityPreprocessorConfig(StrictConfigModel):
    enabled: bool = False


class PreprocessorConfig(StrictConfigModel):
    temporal_window: TemporalWindowPreprocessorConfig
    unit_builder: UnitBuilderPreprocessorConfig
    demand_shape: DemandShapePreprocessorConfig
    drug_grouping: DrugGroupingPreprocessorConfig
    treatment_cycle: TreatmentCyclePreprocessorConfig
    substitution_features: SubstitutionFeaturesPreprocessorConfig
    cohort_context: CohortContextPreprocessorConfig
    seasonality: SeasonalityPreprocessorConfig


class FusionConfig(StrictConfigModel):
    red_score: float = Field(default=75, ge=0, le=100)
    orange_score: float = Field(default=55, ge=0, le=100)
    yellow_score: float = Field(default=35, ge=0, le=100)
    min_confidence_for_alert: float = Field(default=0.3, ge=0, le=1)


class AppConfig(StrictConfigModel):
    config_version: str = "default-v0"
    windows: WindowConfig
    demand_shape: DemandShapeConfig
    preprocessors: PreprocessorConfig
    detectors: DetectorConfig
    fusion: FusionConfig
