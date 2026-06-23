from __future__ import annotations

import pandas as pd

from app.features.snapshot import FeatureSnapshot
from app.preprocessors.base import PreprocessContext


class DrugGroupingPreprocessor:
    name = "drug_grouping"
    version = "v0"
    required_inputs = ["dim_drug", "product_line_mapping", "feature_store"]
    output_features = [
        "product_line_code",
        "product_line_name",
        "generic_name",
        "ingredient_code",
        "function_group_code",
        "treatment_area_code",
    ]
    output_grain = "unit"
    as_of_date_sensitive = False

    def run(self, context: PreprocessContext) -> list[FeatureSnapshot]:
        drugs = context.dim_drug.copy()
        mapping = context.product_line_mapping.copy()
        output: list[FeatureSnapshot] = []
        for snapshot in context.feature_store.query(as_of_date=context.as_of_date):
            warnings: list[str] = []
            features = {
                "product_line_code": None,
                "product_line_name": None,
                "generic_name": None,
                "ingredient_code": None,
                "function_group_code": None,
                "treatment_area_code": None,
            }
            if snapshot.analysis_grain == "product_line":
                features["product_line_code"] = snapshot.target_code
                line_match = mapping[
                    mapping.get("product_line_code", pd.Series(dtype=str)).astype(str)
                    == str(snapshot.target_code)
                ]
                if not line_match.empty and "product_line_name" in line_match.columns:
                    features["product_line_name"] = str(line_match.iloc[0]["product_line_name"])
                else:
                    features["product_line_name"] = snapshot.target_code
                    warnings.append("MISSING_DRUG_GROUP_MAPPING")
            elif snapshot.analysis_grain == "sku":
                drug_match = drugs[drugs.get("drug_code", pd.Series(dtype=str)).astype(str) == snapshot.target_code]
                map_match = mapping[
                    mapping.get("drug_code", pd.Series(dtype=str)).astype(str) == snapshot.target_code
                ]
                if not map_match.empty:
                    features["product_line_code"] = str(map_match.iloc[0].get("product_line_code", ""))
                    features["product_line_name"] = str(map_match.iloc[0].get("product_line_name", ""))
                else:
                    warnings.append("MISSING_DRUG_GROUP_MAPPING")
                if not drug_match.empty and "drug_name" in drug_match.columns:
                    features["generic_name"] = None
            else:
                warnings.append("UNSUPPORTED_GRAIN_FOR_DRUG_GROUPING")
            output.append(snapshot.with_features(features, self.name, self.version, warnings))
        return output
