from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import pandas as pd


class LGBMChurnPredictor:
    model_name = "palive_lgbm"

    def __init__(
        self,
        *,
        model_path: Path,
        feature_columns: list[str],
        model_version: str,
    ) -> None:
        self.model_path = model_path
        self.required_features = feature_columns
        self.model_version = model_version
        with model_path.open("rb") as file:
            self.model: Any = pickle.load(file)

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        missing = [column for column in self.required_features if column not in features.columns]
        if missing:
            raise ValueError("推理特征缺少训练字段: " + ", ".join(missing))
        matrix = features[self.required_features].copy()
        matrix = pd.get_dummies(matrix, dummy_na=True)
        if hasattr(self.model, "feature_names_in_"):
            matrix = matrix.reindex(columns=list(self.model.feature_names_in_), fill_value=0)
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(matrix)
            p_churn = proba[:, 1]
        else:
            raw = self.model.predict(matrix)
            p_churn = raw
        rows = []
        for idx, (_, row) in enumerate(features.iterrows()):
            p_alive = max(0.0, min(1.0, 1.0 - float(p_churn[idx])))
            rows.append(
                {
                    "analysis_unit_id": row["analysis_unit_id"],
                    "org_code": row["org_code"],
                    "org_name": row.get("org_name"),
                    "product_line_code": row["product_line_code"],
                    "product_line_name": row.get("product_line_name"),
                    "selected_model_name": "lgbm_churn_candidate",
                    "p_alive": p_alive,
                    "backbone_risk_score": round((1 - p_alive) * 100, 4),
                    "confidence": 0.6,
                    "warnings": [
                        "PALIVE_LGBM_EXPERIMENTAL_NOT_PRODUCTION_CALIBRATED",
                        "UNCALIBRATED_PALIVE_CANDIDATE",
                    ],
                    "data_sufficiency": {
                        "feature_column_count": len(self.required_features),
                        "confidence_basis": "model_available_but_uncalibrated",
                    },
                }
            )
        return pd.DataFrame(rows)
