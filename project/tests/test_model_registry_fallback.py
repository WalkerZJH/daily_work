from __future__ import annotations

import pandas as pd
import yaml

from app.ml.model_registry import ModelRegistry


def test_model_registry_falls_back_to_interval_proxy_when_active_model_missing(tmp_path) -> None:
    registry_path = tmp_path / "model_registry.yaml"
    registry_path.write_text(
        yaml.safe_dump(
            {
                "active_backbone": "palive_lgbm",
                "models": {
                    "palive_lgbm": {
                        "active_version": "missing",
                        "fallback": "palive_interval_proxy",
                    },
                    "palive_interval_proxy": {"active_version": "builtin"},
                },
            }
        ),
        encoding="utf-8",
    )
    features = pd.DataFrame(
        [
            {
                "analysis_unit_id": "ORG_A|product_line|PL_A",
                "org_code": "ORG_A",
                "product_line_code": "PL_A",
                "days_since_last_purchase": 10,
                "median_interval_days": 30,
                "mean_interval_days": 30,
                "purchase_count_365d": 3,
            }
        ]
    )

    result = ModelRegistry(registry_path=registry_path, artifact_root=tmp_path).load_active_backbone(
        features
    )
    prediction = result.predictor.predict(features)

    assert result.predictor.model_name == "palive_interval_proxy"
    assert "ACTIVE_LGBM_ARTIFACT_MISSING" in result.warnings
    assert prediction.loc[0, "p_alive"] is not None
