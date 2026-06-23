from __future__ import annotations

from app.features.snapshot import FeatureSnapshot
from app.preprocessors.base import PreprocessContext


class SeasonalityPreprocessor:
    name = "seasonality"
    version = "v0"
    required_inputs = ["feature_store"]
    output_features = [
        "same_period_last_year_qty",
        "yoy_qty_ratio",
        "seasonality_confidence",
    ]
    output_grain = "unit"
    as_of_date_sensitive = True

    def run(self, context: PreprocessContext) -> list[FeatureSnapshot]:
        output: list[FeatureSnapshot] = []
        for snapshot in context.feature_store.query(as_of_date=context.as_of_date):
            output.append(
                snapshot.with_features(
                    {
                        "same_period_last_year_qty": None,
                        "yoy_qty_ratio": None,
                        "seasonality_confidence": 0.0,
                    },
                    self.name,
                    self.version,
                    ["INSUFFICIENT_SEASONAL_HISTORY"],
                )
            )
        return output
