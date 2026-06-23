from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FeatureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    dtype: str
    grain: str
    description: str
    produced_by: str
    version: str
    nullable: bool = True


class FeatureCatalog:
    def __init__(self) -> None:
        self._features: dict[str, FeatureSpec] = {}

    def register(self, spec: FeatureSpec) -> None:
        if spec.name in self._features:
            raise ValueError(f"Duplicate feature name: {spec.name}")
        self._features[spec.name] = spec

    def register_many(self, specs: list[FeatureSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def get(self, name: str) -> FeatureSpec:
        return self._features[name]

    def list(self) -> list[FeatureSpec]:
        return list(self._features.values())

    def names(self) -> list[str]:
        return list(self._features.keys())


def build_default_feature_catalog() -> FeatureCatalog:
    catalog = FeatureCatalog()
    catalog.register_many(
        [
            FeatureSpec(
                name="unit_id",
                dtype="str",
                grain="unit",
                description="Stable analysis unit identifier.",
                produced_by="unit_builder",
                version="v0",
                nullable=False,
            ),
            FeatureSpec(
                name="recent_order_count",
                dtype="int",
                grain="unit",
                description="Order count in recent window.",
                produced_by="temporal_window",
                version="v0",
                nullable=False,
            ),
            FeatureSpec(
                name="baseline_order_count",
                dtype="int",
                grain="unit",
                description="Order count in baseline window.",
                produced_by="temporal_window",
                version="v0",
                nullable=False,
            ),
            FeatureSpec(
                name="recent_qty",
                dtype="float",
                grain="unit",
                description="Purchase quantity in recent window.",
                produced_by="temporal_window",
                version="v0",
                nullable=False,
            ),
            FeatureSpec(
                name="baseline_qty",
                dtype="float",
                grain="unit",
                description="Purchase quantity in baseline window.",
                produced_by="temporal_window",
                version="v0",
                nullable=False,
            ),
            FeatureSpec(
                name="recent_active_sku_count",
                dtype="int",
                grain="unit",
                description="Active SKU/spec count in recent window.",
                produced_by="temporal_window",
                version="v0",
                nullable=False,
            ),
            FeatureSpec(
                name="baseline_active_sku_count",
                dtype="int",
                grain="unit",
                description="Active SKU/spec count in baseline window.",
                produced_by="temporal_window",
                version="v0",
                nullable=False,
            ),
            FeatureSpec(
                name="inactive_days",
                dtype="float",
                grain="unit",
                description="Days since last order as of the snapshot date.",
                produced_by="temporal_window",
                version="v0",
            ),
            FeatureSpec(
                name="historical_median_ipi",
                dtype="float",
                grain="unit",
                description="Median historical inter-purchase interval in days.",
                produced_by="temporal_window",
                version="v0",
            ),
            FeatureSpec(
                name="historical_mad_ipi",
                dtype="float",
                grain="unit",
                description="MAD of historical inter-purchase intervals in days.",
                produced_by="temporal_window",
                version="v0",
            ),
            FeatureSpec(
                name="has_recent_order",
                dtype="bool",
                grain="unit",
                description="Whether the unit has orders in the recent window.",
                produced_by="temporal_window",
                version="v0",
                nullable=False,
            ),
            FeatureSpec(
                name="has_baseline_order",
                dtype="bool",
                grain="unit",
                description="Whether the unit has orders in the baseline window.",
                produced_by="temporal_window",
                version="v0",
                nullable=False,
            ),
            FeatureSpec(
                name="first_order_date",
                dtype="date",
                grain="unit",
                description="First order date observed before as_of_date.",
                produced_by="temporal_window",
                version="v0",
            ),
            FeatureSpec(
                name="last_order_date",
                dtype="date",
                grain="unit",
                description="Last order date observed before as_of_date.",
                produced_by="temporal_window",
                version="v0",
            ),
            FeatureSpec(
                name="adi",
                dtype="float",
                grain="unit",
                description="Average demand interval.",
                produced_by="demand_shape",
                version="v0",
            ),
            FeatureSpec(
                name="cv2",
                dtype="float",
                grain="unit",
                description="Squared coefficient of variation.",
                produced_by="demand_shape",
                version="v0",
            ),
            FeatureSpec(
                name="demand_shape",
                dtype="str",
                grain="unit",
                description="smooth / erratic / intermittent / lumpy / unknown.",
                produced_by="demand_shape",
                version="v0",
            ),
            FeatureSpec(
                name="demand_shape_confidence",
                dtype="float",
                grain="unit",
                description="Confidence of demand shape classification.",
                produced_by="demand_shape",
                version="v0",
            ),
            FeatureSpec(
                name="product_line_code",
                dtype="str",
                grain="unit",
                description="Product line code from mapping or fallback.",
                produced_by="drug_grouping",
                version="v0",
            ),
            FeatureSpec(
                name="product_line_name",
                dtype="str",
                grain="unit",
                description="Product line name from mapping or fallback.",
                produced_by="drug_grouping",
                version="v0",
            ),
            FeatureSpec(
                name="generic_name",
                dtype="str",
                grain="unit",
                description="Reserved generic name grouping feature.",
                produced_by="drug_grouping",
                version="v0",
            ),
            FeatureSpec(
                name="ingredient_code",
                dtype="str",
                grain="unit",
                description="Reserved ingredient grouping feature.",
                produced_by="drug_grouping",
                version="v0",
            ),
            FeatureSpec(
                name="function_group_code",
                dtype="str",
                grain="unit",
                description="Reserved function group feature.",
                produced_by="drug_grouping",
                version="v0",
            ),
            FeatureSpec(
                name="treatment_area_code",
                dtype="str",
                grain="unit",
                description="Reserved treatment area feature.",
                produced_by="drug_grouping",
                version="v0",
            ),
            FeatureSpec(
                name="typical_course_days",
                dtype="float",
                grain="unit",
                description="Optional treatment course prior.",
                produced_by="treatment_cycle",
                version="v0",
            ),
            FeatureSpec(
                name="typical_refill_days",
                dtype="float",
                grain="unit",
                description="Optional refill cycle prior.",
                produced_by="treatment_cycle",
                version="v0",
            ),
            FeatureSpec(
                name="cycle_prior_confidence",
                dtype="float",
                grain="unit",
                description="Confidence of cycle prior features.",
                produced_by="treatment_cycle",
                version="v0",
            ),
            FeatureSpec(
                name="chronic_flag",
                dtype="bool",
                grain="unit",
                description="Optional chronic treatment prior flag.",
                produced_by="treatment_cycle",
                version="v0",
            ),
            FeatureSpec(
                name="acute_flag",
                dtype="bool",
                grain="unit",
                description="Optional acute treatment prior flag.",
                produced_by="treatment_cycle",
                version="v0",
            ),
            FeatureSpec(
                name="seasonality_flag",
                dtype="bool",
                grain="unit",
                description="Optional seasonality prior flag.",
                produced_by="treatment_cycle",
                version="v0",
            ),
            FeatureSpec(
                name="stockpile_flag",
                dtype="bool",
                grain="unit",
                description="Optional stockpile prior flag.",
                produced_by="treatment_cycle",
                version="v0",
            ),
            FeatureSpec(
                name="same_group_recent_qty",
                dtype="float",
                grain="unit",
                description="Recent quantity for same-group products.",
                produced_by="substitution_features",
                version="v0",
            ),
            FeatureSpec(
                name="same_group_baseline_qty",
                dtype="float",
                grain="unit",
                description="Baseline quantity for same-group products.",
                produced_by="substitution_features",
                version="v0",
            ),
            FeatureSpec(
                name="own_recent_qty",
                dtype="float",
                grain="unit",
                description="Recent quantity for the current target.",
                produced_by="substitution_features",
                version="v0",
            ),
            FeatureSpec(
                name="own_baseline_qty",
                dtype="float",
                grain="unit",
                description="Baseline quantity for the current target.",
                produced_by="substitution_features",
                version="v0",
            ),
            FeatureSpec(
                name="substitute_candidate_count",
                dtype="int",
                grain="unit",
                description="Observable same-group substitute candidate count.",
                produced_by="substitution_features",
                version="v0",
            ),
            FeatureSpec(
                name="substitute_qty_delta",
                dtype="float",
                grain="unit",
                description="Quantity delta for substitution-oriented features.",
                produced_by="substitution_features",
                version="v0",
            ),
            FeatureSpec(
                name="substitution_feature_confidence",
                dtype="float",
                grain="unit",
                description="Confidence of substitution-oriented features.",
                produced_by="substitution_features",
                version="v0",
            ),
            FeatureSpec(
                name="org_level",
                dtype="str",
                grain="unit",
                description="Organization level context.",
                produced_by="cohort_context",
                version="v0",
            ),
            FeatureSpec(
                name="region_code",
                dtype="str",
                grain="unit",
                description="Organization region context.",
                produced_by="cohort_context",
                version="v0",
            ),
            FeatureSpec(
                name="cohort_key",
                dtype="str",
                grain="unit",
                description="Simple cohort key.",
                produced_by="cohort_context",
                version="v0",
            ),
            FeatureSpec(
                name="cohort_size",
                dtype="int",
                grain="unit",
                description="Number of units in the simple cohort.",
                produced_by="cohort_context",
                version="v0",
            ),
            FeatureSpec(
                name="cohort_recent_qty_median",
                dtype="float",
                grain="unit",
                description="Median recent quantity in the simple cohort.",
                produced_by="cohort_context",
                version="v0",
            ),
            FeatureSpec(
                name="cohort_baseline_qty_median",
                dtype="float",
                grain="unit",
                description="Median baseline quantity in the simple cohort.",
                produced_by="cohort_context",
                version="v0",
            ),
            FeatureSpec(
                name="same_period_last_year_qty",
                dtype="float",
                grain="unit",
                description="Same-period last-year quantity when sufficient history exists.",
                produced_by="seasonality",
                version="v0",
            ),
            FeatureSpec(
                name="yoy_qty_ratio",
                dtype="float",
                grain="unit",
                description="Year-over-year quantity ratio when sufficient history exists.",
                produced_by="seasonality",
                version="v0",
            ),
            FeatureSpec(
                name="seasonality_confidence",
                dtype="float",
                grain="unit",
                description="Reserved seasonality confidence.",
                produced_by="seasonality",
                version="v0",
            ),
        ]
    )
    return catalog
