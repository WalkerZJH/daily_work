from __future__ import annotations

import pandas as pd

from app.features.snapshot import FeatureSnapshot
from app.preprocessors.base import PreprocessContext, unit_id


class UnitBuilderPreprocessor:
    name = "unit_builder"
    version = "v0"
    required_inputs = ["canonical_orders"]
    output_features = ["unit_id"]
    output_grain = "unit"
    as_of_date_sensitive = True

    def run(self, context: PreprocessContext) -> list[FeatureSnapshot]:
        orders = context.canonical_orders.copy()
        orders["order_time"] = pd.to_datetime(orders["order_time"], errors="coerce")
        orders = orders[orders["order_time"].notna()]
        orders = orders[orders["order_time"].dt.date <= context.as_of_date]

        grains = context.config.preprocessors.unit_builder.grains
        snapshots: list[FeatureSnapshot] = []
        if "product_line" in grains and "product_line_code" in orders.columns:
            units = orders[["org_code", "product_line_code"]].dropna().drop_duplicates()
            for _, row in units.iterrows():
                org_code = str(row["org_code"])
                target_code = str(row["product_line_code"])
                snapshots.append(
                    self._snapshot(context, org_code, "product_line", target_code)
                )
        if "sku" in grains:
            units = orders[["org_code", "drug_code"]].dropna().drop_duplicates()
            for _, row in units.iterrows():
                org_code = str(row["org_code"])
                target_code = str(row["drug_code"])
                snapshots.append(self._snapshot(context, org_code, "sku", target_code))
        return snapshots

    def _snapshot(
        self,
        context: PreprocessContext,
        org_code: str,
        analysis_grain: str,
        target_code: str,
    ) -> FeatureSnapshot:
        uid = unit_id(org_code, analysis_grain, target_code)
        return FeatureSnapshot(
            unit_id=uid,
            org_code=org_code,
            analysis_grain=analysis_grain,
            target_code=target_code,
            as_of_date=context.as_of_date,
            features={"unit_id": uid},
            feature_versions={"unit_id": self.version},
            produced_by={"unit_id": self.name},
        )
