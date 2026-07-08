from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from risk_model_core import ParquetRiskResultRepository  # noqa: E402
from risk_model_core.page_payload_builder import PagePayloadBuilder  # noqa: E402

try:  # noqa: E402
    from risk_model_core.page_payload_builder import build_default_frontend_payloads  # type: ignore[attr-defined]
except ImportError:  # noqa: E402
    from app.services.frontend_default_payloads import build_default_frontend_payloads


DEFAULT_MODEL_METRICS: list[dict[str, Any]] = [
    {
        "model_id": "backbone_xgboost_h3",
        "model_name": "主干风险模型 H3",
        "model_role": "backbone_risk_probability",
        "horizon": "H3",
        "evaluation_window": "2020-2025 rolling backtest",
        "auc": 0.812,
        "prauc": 0.776,
        "pr_auc_lift": 1.610,
        "ece": 0.024,
        "brier": 0.177,
        "topk_recall": [
            {
                "label": "前10%名单",
                "requested_k_percent": 0.10,
                "actual_k_percent": 0.1000,
                "selected_count": 52506,
                "evaluation_population": 524950,
                "true_positive_count": 45647,
                "recall": 0.1796,
                "k_policy": "direct_actual_share",
            },
        ],
        "sample_count": 524950,
        "positive_count": 253094,
        "updated_at": "2026-07-08",
    },
    {
        "model_id": "backbone_xgboost_h6",
        "model_name": "主干风险模型 H6",
        "model_role": "backbone_risk_probability",
        "horizon": "H6",
        "evaluation_window": "2020-2025 rolling backtest",
        "auc": 0.814,
        "prauc": 0.686,
        "pr_auc_lift": 1.857,
        "ece": 0.022,
        "brier": 0.169,
        "topk_recall": [
            {
                "label": "前10%名单",
                "requested_k_percent": 0.10,
                "actual_k_percent": 0.1000,
                "selected_count": 52506,
                "evaluation_population": 524950,
                "true_positive_count": 41136,
                "recall": 0.2112,
                "k_policy": "direct_actual_share",
            }
        ],
        "sample_count": 524950,
        "positive_count": 193976,
        "updated_at": "2026-07-08",
    },
    {
        "model_id": "backbone_xgboost_h12",
        "model_name": "主干风险模型 H12",
        "model_role": "backbone_risk_probability",
        "horizon": "H12",
        "evaluation_window": "2020-2025 rolling backtest",
        "auc": 0.814,
        "prauc": 0.598,
        "pr_auc_lift": 2.090,
        "ece": 0.023,
        "brier": 0.154,
        "topk_recall": [
            {
                "label": "前10%名单",
                "requested_k_percent": 0.10,
                "actual_k_percent": 0.1000,
                "selected_count": 36954,
                "evaluation_population": 369465,
                "true_positive_count": 25494,
                "recall": 0.2395,
                "k_policy": "direct_actual_share",
            }
        ],
        "sample_count": 369465,
        "positive_count": 105743,
        "updated_at": "2026-07-08",
    },
    {
        "model_id": "oneshot_repurchase_h6",
        "model_name": "新进终端复购倾向 H6",
        "model_role": "oneshot_repurchase_propensity",
        "horizon": "H6",
        "evaluation_window": "first-purchase cohort backtest",
        "auc": 0.307,
        "prauc": 0.264,
        "pr_auc_lift": 0.725,
        "ece": 0.321,
        "brier": 0.352,
        "topk_recall": [],
        "sample_count": 83824,
        "positive_count": 30478,
        "updated_at": "2026-07-08",
    },
    {
        "model_id": "frequency_detector_evidence",
        "model_name": "采购频次证据模块",
        "model_role": "detector_evidence",
        "horizon": "H6",
        "evaluation_window": "detector evidence hit backtest",
        "auc": 0.672,
        "prauc": 0.516,
        "pr_auc_lift": 1.324,
        "ece": 0.312,
        "brier": 0.312,
        "topk_recall": [
            {
                "label": "证据命中集合",
                "requested_k_percent": 0.3892,
                "actual_k_percent": 0.3892,
                "selected_count": 552406,
                "evaluation_population": 1419365,
                "true_positive_count": 331315,
                "recall": 0.5993,
                "k_policy": "direct_actual_share",
            }
        ],
        "sample_count": 1419365,
        "positive_count": 552790,
        "updated_at": "2026-07-08",
    },
    {
        "model_id": "interval_detector_evidence",
        "model_name": "采购间隔证据模块",
        "model_role": "detector_evidence",
        "horizon": "H6",
        "evaluation_window": "detector evidence hit backtest",
        "auc": 0.583,
        "prauc": 0.449,
        "pr_auc_lift": 1.152,
        "ece": 0.355,
        "brier": 0.355,
        "topk_recall": [
            {
                "label": "证据命中集合",
                "requested_k_percent": 0.2031,
                "actual_k_percent": 0.2031,
                "selected_count": 288304,
                "evaluation_population": 1419365,
                "true_positive_count": 168415,
                "recall": 0.3046,
                "k_policy": "direct_actual_share",
            }
        ],
        "sample_count": 1419365,
        "positive_count": 552790,
        "updated_at": "2026-07-08",
    },
]


class FrontendPageService:
    def __init__(self, batch_dir: str | Path | None = None):
        self.batch_dir = Path(batch_dir) if batch_dir else None
        self._default_payloads = build_default_frontend_payloads()
        self._builder = self._build_batch_payload_builder(self.batch_dir)

    def workbench(self) -> dict[str, Any]:
        if self._builder:
            return self._with_model_metrics(self._builder.build_frontend_workbench_payload())
        return self._with_model_metrics(self._default_payloads["workbench"])

    def risk_entities(self) -> dict[str, Any]:
        if self._builder:
            return self._builder.build_frontend_risk_entities_payload()
        return self._default_payloads["risk_entities"]

    def risk_entity_detail(self, entity_id: str) -> dict[str, Any]:
        if self._builder:
            return self._builder.build_frontend_risk_entity_detail_payload(entity_id)
        details = self._default_payloads["risk_entity_details"]
        if entity_id not in details:
            raise KeyError(entity_id)
        return details[entity_id]

    def oneshot_terminals(self) -> dict[str, Any]:
        if self._builder:
            return self._builder.build_frontend_oneshot_payload()
        return self._default_payloads["oneshot_terminals"]

    def monthly_reports(self) -> dict[str, Any]:
        if self._builder:
            return self._with_model_metrics(self._builder.build_frontend_monthly_reports_payload())
        return self._with_model_metrics(self._default_payloads["monthly_reports"])

    def proof_cases(self) -> dict[str, Any]:
        if self._builder:
            return self._builder.build_frontend_proof_cases_payload()
        return self._default_payloads["proof_cases"]

    @staticmethod
    def _build_batch_payload_builder(batch_dir: Path | None) -> PagePayloadBuilder | None:
        if not batch_dir or not batch_dir.exists():
            return None
        return PagePayloadBuilder(ParquetRiskResultRepository(batch_dir))

    @staticmethod
    def _with_model_metrics(payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("model_metrics"):
            return payload
        return {**payload, "model_metrics": DEFAULT_MODEL_METRICS}


@lru_cache(maxsize=1)
def get_frontend_page_service() -> FrontendPageService:
    return FrontendPageService(os.getenv("RISK_RESULT_BATCH_DIR"))
