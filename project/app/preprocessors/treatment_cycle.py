from __future__ import annotations

from app.features.snapshot import FeatureSnapshot
from app.preprocessors.base import PreprocessContext


class TreatmentCyclePreprocessor:
    name = "treatment_cycle"
    version = "v0"
    required_inputs = ["feature_store"]
    output_features = [
        "typical_course_days",
        "typical_refill_days",
        "chronic_flag",
        "acute_flag",
        "seasonality_flag",
        "stockpile_flag",
        "cycle_prior_confidence",
    ]
    output_grain = "unit"
    as_of_date_sensitive = False

    def run(self, context: PreprocessContext) -> list[FeatureSnapshot]:
        cycle_table = context.optional_tables.get("dim_drug_cycle")
        output: list[FeatureSnapshot] = []
        missing = cycle_table is None or cycle_table.empty
        for snapshot in context.feature_store.query(as_of_date=context.as_of_date):
            warnings = ["MISSING_TREATMENT_CYCLE_PRIOR"] if missing else []
            features = {
                "typical_course_days": None,
                "typical_refill_days": None,
                "chronic_flag": None,
                "acute_flag": None,
                "seasonality_flag": None,
                "stockpile_flag": None,
                "cycle_prior_confidence": 0.0 if missing else 0.5,
            }
            output.append(snapshot.with_features(features, self.name, self.version, warnings))
        return output
