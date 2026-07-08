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
from risk_model_core.page_payload_builder import PagePayloadBuilder, build_default_frontend_payloads  # noqa: E402


DEFAULT_MODEL_METRICS: list[dict[str, Any]] = [
    {
        "model_id": "backbone_xgboost_h6",
        "model_name": "主干风险概率模型",
        "model_role": "backbone_risk_probability",
        "horizon": "H6",
        "evaluation_window": "2026-01 to 2026-06 walk-forward",
        "auc": 0.842,
        "prauc": 0.318,
        "ece": 0.037,
        "brier": 0.109,
        "topk_recall": [
            {
                "label": "Top 5%",
                "requested_k_percent": 0.05,
                "actual_k_percent": 0.0503,
                "selected_count": 410,
                "evaluation_population": 8148,
                "true_positive_count": 126,
                "recall": 0.412,
                "k_policy": "direct_actual_share",
            },
            {
                "label": "Top 10%",
                "requested_k_percent": 0.10,
                "actual_k_percent": 0.1001,
                "selected_count": 816,
                "evaluation_population": 8148,
                "true_positive_count": 191,
                "recall": 0.624,
                "k_policy": "direct_actual_share",
            },
        ],
        "sample_count": 8148,
        "positive_count": 306,
        "updated_at": "2026-07-07 13:32",
    },
    {
        "model_id": "oneshot_repurchase_propensity",
        "model_name": "oneshot 复购倾向模型",
        "model_role": "oneshot_repurchase_propensity",
        "horizon": "H6",
        "evaluation_window": "2026-01 to 2026-06 first-purchase cohorts",
        "auc": 0.806,
        "prauc": 0.441,
        "ece": 0.043,
        "brier": 0.137,
        "topk_recall": [
            {
                "label": "Top 10%",
                "requested_k_percent": 0.10,
                "actual_k_percent": 0.0996,
                "selected_count": 186,
                "evaluation_population": 1867,
                "true_positive_count": 71,
                "recall": 0.533,
                "k_policy": "direct_actual_share",
            }
        ],
        "sample_count": 1867,
        "positive_count": 133,
        "updated_at": "2026-07-07 13:32",
    },
    {
        "model_id": "detector_evidence_ranker",
        "model_name": "detector 证据排序模型",
        "model_role": "detector_evidence_ranker",
        "horizon": "H6",
        "evaluation_window": "2026-01 to 2026-06 detector evidence backtest",
        "auc": 0.781,
        "prauc": 0.294,
        "ece": 0.052,
        "brier": 0.128,
        "topk_recall": [
            {
                "label": "Union TopK actual 12.8%",
                "requested_k_percent": 0.10,
                "actual_k_percent": 0.128,
                "selected_count": 1043,
                "evaluation_population": 8148,
                "true_positive_count": 213,
                "recall": 0.696,
                "k_policy": "union_backfilled_actual_share",
            }
        ],
        "sample_count": 8148,
        "positive_count": 306,
        "updated_at": "2026-07-07 13:32",
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
