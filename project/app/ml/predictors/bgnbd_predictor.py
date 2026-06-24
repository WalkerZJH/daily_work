from __future__ import annotations

import pandas as pd


class BGNBDPredictor:
    model_name = "palive_bgnbd"
    model_version = "candidate"
    required_features = ["purchase_count_365d", "days_since_last_purchase"]

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for _, row in features.iterrows():
            rows.append(
                {
                    "analysis_unit_id": row["analysis_unit_id"],
                    "org_code": row["org_code"],
                    "product_line_code": row["product_line_code"],
                    "p_alive": None,
                    "backbone_risk_score": None,
                    "confidence": 0.0,
                    "warnings": [
                        "BGNBD_CANDIDATE_NOT_TRAINED",
                        "PALIVE_NOT_CALIBRATED_AS_PROBABILITY",
                    ],
                }
            )
        return pd.DataFrame(rows)
