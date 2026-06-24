from __future__ import annotations

import pandas as pd


class IntervalProxyPredictor:
    model_name = "palive_interval_proxy"
    model_version = "builtin"
    required_features = ["days_since_last_purchase", "median_interval_days", "mean_interval_days"]

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for _, row in features.iterrows():
            days = _float(row.get("days_since_last_purchase"))
            interval = _float(row.get("median_interval_days")) or _float(row.get("mean_interval_days"))
            warnings = [
                "FALLBACK_INTERVAL_PROXY_USED",
                "UNCALIBRATED_PALIVE_CANDIDATE",
            ]
            if days is None or interval is None or interval <= 0:
                p_alive = None
                confidence = 0.1
                warnings.append("INTERVAL_PROXY_INSUFFICIENT_FEATURES")
            else:
                overdue_ratio = days / interval
                p_alive = max(0.0, min(1.0, 1.0 / (1.0 + max(0.0, overdue_ratio - 0.5))))
                confidence = 0.35 if row.get("purchase_count_365d", 0) and row.get("purchase_count_365d", 0) >= 2 else 0.2
            rows.append(
                {
                    "analysis_unit_id": row["analysis_unit_id"],
                    "org_code": row["org_code"],
                    "org_name": row.get("org_name"),
                    "product_line_code": row["product_line_code"],
                    "product_line_name": row.get("product_line_name"),
                    "selected_model_name": "interval_survival_proxy",
                    "p_alive": p_alive,
                    "backbone_risk_score": None if p_alive is None else round((1 - p_alive) * 100, 4),
                    "confidence": confidence,
                    "warnings": warnings,
                    "data_sufficiency": {
                        "purchase_count_365d": _int(row.get("purchase_count_365d")),
                        "has_interval_feature": interval is not None,
                        "confidence_basis": "low_confidence_interval_proxy",
                    },
                }
            )
        return pd.DataFrame(rows)


def _float(value) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0
