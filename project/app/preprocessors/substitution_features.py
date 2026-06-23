from __future__ import annotations

from app.features.snapshot import FeatureSnapshot
from app.preprocessors.base import PreprocessContext


class SubstitutionFeaturePreprocessor:
    name = "substitution_features"
    version = "v0"
    required_inputs = ["feature_store"]
    output_features = [
        "same_group_recent_qty",
        "same_group_baseline_qty",
        "own_recent_qty",
        "own_baseline_qty",
        "substitute_candidate_count",
        "substitute_qty_delta",
        "substitution_feature_confidence",
    ]
    output_grain = "unit"
    as_of_date_sensitive = True

    def run(self, context: PreprocessContext) -> list[FeatureSnapshot]:
        output: list[FeatureSnapshot] = []
        for snapshot in context.feature_store.query(as_of_date=context.as_of_date):
            recent_qty = float(snapshot.features.get("recent_qty") or 0)
            baseline_qty = float(snapshot.features.get("baseline_qty") or 0)
            features = {
                "same_group_recent_qty": recent_qty,
                "same_group_baseline_qty": baseline_qty,
                "own_recent_qty": recent_qty,
                "own_baseline_qty": baseline_qty,
                "substitute_candidate_count": 0,
                "substitute_qty_delta": 0.0,
                "substitution_feature_confidence": 0.1,
            }
            output.append(
                snapshot.with_features(
                    features,
                    self.name,
                    self.version,
                    ["LIMITED_TO_OWN_PRODUCTS"],
                )
            )
        return output
