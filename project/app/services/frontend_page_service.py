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
from risk_model_core import RiskResultRepository  # noqa: E402
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
    def __init__(
        self,
        batch_dir: str | Path | None = None,
        repository: RiskResultRepository | None = None,
    ):
        self.batch_dir = Path(batch_dir) if batch_dir else None
        self._repository = repository
        self._mock_allowed = os.getenv("ALLOW_MOCK_PAYLOADS", "").lower() == "true"
        self._default_payloads = build_default_frontend_payloads()
        self._builder = PagePayloadBuilder(repository) if repository is not None else self._build_batch_payload_builder(self.batch_dir)

    def workbench(self) -> dict[str, Any]:
        if self._builder:
            return _strip_customer_hidden_fields(self._builder.build_frontend_workbench_payload())
        if self._mock_allowed:
            return _mock_payload(_strip_customer_hidden_fields(self._default_payloads["workbench"]))
        return _formal_unavailable_workbench()

    def risk_entities(self) -> dict[str, Any]:
        if self._builder:
            return _strip_customer_hidden_fields(self._builder.build_frontend_risk_entities_payload())
        return _strip_customer_hidden_fields(self._default_payloads["risk_entities"])

    def risk_entity_detail(self, entity_id: str, *, horizon: str = "H6") -> dict[str, Any]:
        if self._builder:
            return self._select_horizon(
                _strip_customer_hidden_fields(self._builder.build_frontend_risk_entity_detail_payload(entity_id)),
                horizon,
            )
        details = self._default_payloads["risk_entity_details"]
        if entity_id not in details:
            raise KeyError(entity_id)
        return self._select_horizon(_strip_customer_hidden_fields(details[entity_id]), horizon)

    def probability_trend(self, entity_id: str, *, horizon: str = "H6") -> dict[str, Any]:
        if self._builder:
            repository = self._builder.repository
            profiles = repository.list_risk_entity_horizon_profiles(
                risk_entity_id=entity_id,
                horizon=horizon,
            )
            if profiles.empty and repository.get_risk_entity(entity_id) is None:
                raise KeyError(entity_id)
            items = [
                {
                    "report_month": str(row.get("report_month")),
                    "horizon": str(row.get("horizon")),
                    "risk_probability": _number_or_none(row.get("risk_probability")),
                    "involved_amount": _int_or_zero(row.get("involved_amount")),
                    "involved_amount_source": _text(row.get("involved_amount_source")),
                    "reason": _text(row.get("reason") or row.get("main_reason_summary")),
                    "updated_at": _text(row.get("updated_at")),
                }
                for _, row in profiles.sort_values("report_month", kind="mergesort").iterrows()
            ]
            return {
                "risk_entity_id": entity_id,
                "horizon": horizon,
                "items": items,
                "warnings": [] if items else ["HORIZON_PROFILE_NOT_AVAILABLE"],
            }
        detail = self.risk_entity_detail(entity_id, horizon=horizon)
        profile = detail.get("selected_horizon_profile") or {}
        return {
            "risk_entity_id": entity_id,
            "horizon": horizon,
            "items": [
                {
                    "report_month": detail.get("entity", {}).get("report_month", ""),
                    "horizon": horizon,
                    "risk_probability": profile.get("risk_probability"),
                    "involved_amount": profile.get("involved_amount", 0),
                    "involved_amount_source": profile.get("involved_amount_source", ""),
                    "reason": profile.get("reason", ""),
                    "updated_at": profile.get("updated_at", ""),
                }
            ],
            "warnings": ["DEFAULT_PAYLOAD_TREND_SINGLE_POINT"],
        }

    def oneshot_terminals(
        self,
        *,
        manufacturer_codes: list[str] | None = None,
        report_month: str | None = None,
        horizon: str | None = None,
        top_n: int | None = None,
    ) -> dict[str, Any]:
        if self._builder:
            return self._builder.build_frontend_oneshot_payload(
                manufacturer_codes=manufacturer_codes,
                report_month=report_month,
                horizon=horizon,
                top_n=top_n,
            )
        return self._default_payloads["oneshot_terminals"]

    def monthly_reports(self) -> dict[str, Any]:
        if self._builder:
            return _strip_customer_hidden_fields(self._builder.build_frontend_monthly_reports_payload())
        return _strip_customer_hidden_fields(self._default_payloads["monthly_reports"])

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
    def _select_horizon(payload: dict[str, Any], horizon: str) -> dict[str, Any]:
        profiles = payload.get("horizon_profiles") or {}
        profile = profiles.get(horizon) or next(iter(profiles.values()), {})
        entity = dict(payload.get("entity") or {})
        if profile:
            entity["horizon"] = horizon
            if profile.get("risk_probability") is not None:
                entity["risk_probability"] = profile.get("risk_probability")
            entity["involved_amount"] = _int_or_zero(profile.get("involved_amount"))
            entity["involved_amount_source"] = _text(profile.get("involved_amount_source"))
            entity["average_consumption_in_window"] = _int_or_zero(profile.get("involved_amount"))
            entity["primary_reason"] = _text(profile.get("reason") or profile.get("main_reason_summary") or entity.get("primary_reason"))
            if profile.get("risk_band"):
                entity["risk_band"] = profile.get("risk_band")
        return {
            **payload,
            "entity": entity,
            "selected_horizon": horizon,
            "selected_horizon_profile": profile,
        }


@lru_cache(maxsize=1)
def get_frontend_page_service() -> FrontendPageService:
    return FrontendPageService(_default_batch_dir())


def _default_batch_dir() -> str | Path | None:
    batch_root = os.getenv("RISK_RESULT_BATCH_ROOT")
    if batch_root:
        manifests = sorted(Path(batch_root).glob("report_month=*/batch_id=*/manifest.json"))
        if manifests:
            return manifests[-1].parent
        return None
    return os.getenv("RISK_RESULT_BATCH_DIR")


def _strip_customer_hidden_fields(value: Any) -> Any:
    hidden = {
        "business_score",
        "monthly_loss_value",
        "expected_loss",
        "model_metrics",
        "fill_policy",
        "fill_source",
        "risk_probability_value",
        "churn_probability_H",
        "risk_score",
        "risk_score_display",
        "probability_rank_score",
        "interval_rank_score",
        "frequency_rank_score",
        "business_priority_score_H",
        "value_at_risk_H",
    }
    if isinstance(value, dict):
        return {key: _strip_customer_hidden_fields(item) for key, item in value.items() if key not in hidden}
    if isinstance(value, list):
        return [_strip_customer_hidden_fields(item) for item in value]
    return value


def _mock_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        **payload,
        "ready": False,
        "data_source": "mock",
        "demo_mode": True,
        "monthly_risk_entities": payload.get("rows", []),
        "today_high_score_rule_clues": [],
        "today_clue_count": 0,
        "highest_detector_score": None,
        "priority_risk_entity_count": len(payload.get("rows", [])),
        "warnings": ["MOCK_PAYLOADS_EXPLICITLY_ENABLED"],
    }


def _formal_unavailable_workbench() -> dict[str, Any]:
    return {
        "ready": False,
        "data_source": "unavailable",
        "demo_mode": False,
        "batch_context": {
            "report_month": "",
            "score_as_of_date": "",
            "data_watermark_at": "",
            "score_batch_id": "",
            "result_batch_id": "",
            "primary_horizon": "H6",
            "primary_horizon_label": "H6",
            "involved_amount_definition": "selected horizon window consumption",
        },
        "overview_metrics": [],
        "rows": [],
        "scope": {"manufacturer_count": 0, "manufacturer_codes": []},
        "query": {"horizon": "H6", "top_n": 20, "sort_by": "risk_probability"},
        "detector_summary": {
            "detector_clue_count": 0,
            "latest_detector_run_date": None,
            "detector_status_summary": "missing",
        },
        "current_user_id": None,
        "current_manufacturer_code": None,
        "current_observation_date": None,
        "horizon": "H6",
        "top_n": 20,
        "sort_by": "risk_probability",
        "today_clue_count": 0,
        "highest_detector_score": None,
        "priority_risk_entity_count": 0,
        "today_high_score_rule_clues": [],
        "monthly_risk_entities": [],
        "warnings": ["RISK_RESULT_BATCH_DIR_NOT_CONFIGURED"],
    }


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _int_or_zero(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _number_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
