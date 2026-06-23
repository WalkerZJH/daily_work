from __future__ import annotations

import pandas as pd

from app.features.snapshot import FeatureSnapshot
from app.preprocessors.base import PreprocessContext


class CohortContextPreprocessor:
    name = "cohort_context"
    version = "v0"
    required_inputs = ["dim_org", "feature_store"]
    output_features = [
        "org_level",
        "region_code",
        "cohort_key",
        "cohort_size",
        "cohort_recent_qty_median",
        "cohort_baseline_qty_median",
    ]
    output_grain = "unit"
    as_of_date_sensitive = True

    def run(self, context: PreprocessContext) -> list[FeatureSnapshot]:
        orgs = context.dim_org.copy()
        snapshots = context.feature_store.query(as_of_date=context.as_of_date)
        qty_by_cohort: dict[str, list[tuple[float, float]]] = {}
        profile_by_org: dict[str, tuple[str | None, str | None]] = {}
        for _, row in orgs.iterrows():
            org_code = str(row.get("org_code", ""))
            org_level = row.get("org_level")
            region_code = row.get("region_code")
            profile_by_org[org_code] = (
                None if pd.isna(org_level) else str(org_level),
                None if pd.isna(region_code) else str(region_code),
            )
        for snapshot in snapshots:
            org_level, region_code = profile_by_org.get(snapshot.org_code, (None, None))
            cohort_key = f"{region_code or 'UNKNOWN'}|{org_level or 'UNKNOWN'}"
            qty_by_cohort.setdefault(cohort_key, []).append(
                (
                    float(snapshot.features.get("recent_qty") or 0),
                    float(snapshot.features.get("baseline_qty") or 0),
                )
            )

        output: list[FeatureSnapshot] = []
        for snapshot in snapshots:
            org_level, region_code = profile_by_org.get(snapshot.org_code, (None, None))
            cohort_key = f"{region_code or 'UNKNOWN'}|{org_level or 'UNKNOWN'}"
            cohort_values = qty_by_cohort.get(cohort_key, [])
            recent_values = [item[0] for item in cohort_values]
            baseline_values = [item[1] for item in cohort_values]
            features = {
                "org_level": org_level,
                "region_code": region_code,
                "cohort_key": cohort_key,
                "cohort_size": len(cohort_values),
                "cohort_recent_qty_median": float(pd.Series(recent_values).median()) if recent_values else None,
                "cohort_baseline_qty_median": float(pd.Series(baseline_values).median()) if baseline_values else None,
            }
            output.append(snapshot.with_features(features, self.name, self.version))
        return output
