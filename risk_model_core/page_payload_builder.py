"""Page payload builder for backend MVC integration.

The builder serves standard result batches. It never reads source business
tables, never recalculates model output, and never resolves real user scope.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
import math

import pandas as pd

from .repositories import RiskResultRepository


OPTIONAL_RANKING_FIELDS = [
    "risk_probability_value",
    "churn_probability_H",
    "risk_score_display",
    "risk_score",
    "probability_rank_score",
    "interval_rank_score",
    "frequency_rank_score",
    "business_priority_score_H",
    "value_at_risk_H",
    "overdue_ratio",
    "frequency_decay_baseline",
    "interval_overdue_baseline",
    "recency_only_baseline",
    "candidate_type",
    "display_section",
    "probability_display_level",
]

DETECTOR_TEMPLATES = [
    ("purchase_gap", "Purchase gap", "purchase_interval_overdue_warning"),
    ("frequency_drop", "Frequency drop", "purchase_frequency_fluctuation_warning"),
    ("quantity_drop", "Quantity drop", "purchase_quantity_fluctuation_warning"),
    ("terminal_loss", "Stored terminal risk", "terminal_loss_warning"),
    ("new_terminal", "New terminal", "new_terminal_detection"),
    ("delivery_time", "Delivery timing", ""),
    ("delivery_rate", "Delivery fulfillment", ""),
    ("price_signal", "Price signal", ""),
    ("sku_wallet", "Portfolio signal", ""),
]


class PagePayloadBuilder:
    def __init__(self, repository: RiskResultRepository, *, prefer_existing_payloads: bool = True):
        self.repository = repository
        self.prefer_existing_payloads = prefer_existing_payloads

    def build_index_payload(self) -> dict[str, Any]:
        return self._payload_or_build("index_payload", self._build_index_payload)

    def build_clues_payload(self) -> dict[str, Any]:
        return self._payload_or_build("clues_payload", self._build_clues_payload)

    def build_clue_detail_payload(self, risk_entity_id: str) -> dict[str, Any]:
        entity = self.repository.get_risk_entity(risk_entity_id)
        if entity is None:
            raise KeyError(risk_entity_id)
        cards = self.repository.list_risk_cards(risk_entity_id).to_dict("records")
        for card in cards:
            card["evidence"] = self.repository.list_evidence(str(card["risk_card_id"])).to_dict("records")
        return {"risk_entity": entity, "risk_cards": cards, "auto_dispatch_allowed": False}

    def build_watchlist_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "watchlist_payload",
            lambda: {"items": self.repository.list_rankable_entities(candidate_type="observation").to_dict("records")},
        )

    def build_dashboard_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "dashboard_payload",
            lambda: {"kpi_cards": self._dashboard_metrics()},
        )

    def build_backtest_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "backtest_payload",
            lambda: {"proof_case_report_allowed": False, "items": self.repository.list_proof_cases().to_dict("records")},
        )

    def build_verify_payload(self) -> dict[str, Any]:
        return self._payload_or_build("verify_payload", lambda: {"verification_enabled": False, "items": []})

    def build_distributor_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "distributor_payload",
            lambda: {"delivery_detector_enabled": False, "alerts": []},
        )

    def build_frontend_workbench_payload(
        self,
        *,
        manufacturer_codes: list[str] | None = None,
        report_month: str | None = None,
        horizon: str | None = None,
        top_n: int | None = None,
    ) -> dict[str, Any]:
        return self._payload_or_build(
            "frontend_workbench_payload",
            lambda: self._build_frontend_workbench_payload(
                manufacturer_codes=manufacturer_codes,
                report_month=report_month,
                horizon=horizon,
                top_n=top_n,
            ),
        )

    def build_frontend_risk_entities_payload(
        self,
        *,
        manufacturer_codes: list[str] | None = None,
        report_month: str | None = None,
        horizon: str | None = None,
        top_n: int | None = None,
    ) -> dict[str, Any]:
        return self._payload_or_build(
            "frontend_risk_entities_payload",
            lambda: self._build_frontend_risk_entities_payload(
                manufacturer_codes=manufacturer_codes,
                report_month=report_month,
                horizon=horizon,
                top_n=top_n,
            ),
        )

    def build_frontend_risk_entity_detail_payload(self, risk_entity_id: str) -> dict[str, Any]:
        if self.prefer_existing_payloads:
            try:
                return self.repository.get_page_payload(f"frontend_risk_entity_detail_{risk_entity_id}_payload")
            except FileNotFoundError:
                try:
                    manifest = self.repository.get_page_payload("frontend_payload_manifest")
                    for item in manifest.get("detail_payloads", []):
                        if str(item.get("entity_id")) == str(risk_entity_id):
                            return self.repository.get_page_payload(str(item["detail_payload_file"]))
                except FileNotFoundError:
                    pass
        return self._build_frontend_risk_entity_detail_payload(risk_entity_id)

    def build_frontend_oneshot_payload(
        self,
        *,
        manufacturer_codes: list[str] | None = None,
        report_month: str | None = None,
        observation_date: str | None = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "first_purchase_date",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        # One-shot is a formal fact table.  Do not serve a cached legacy page
        # payload because older payloads contain prediction-like semantics.
        return self._build_frontend_oneshot_payload(
            manufacturer_codes=manufacturer_codes,
            report_month=report_month,
            observation_date=observation_date,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def build_frontend_monthly_reports_payload(self) -> dict[str, Any]:
        return self._payload_or_build("frontend_monthly_reports_payload", self._build_frontend_monthly_reports_payload)

    def build_frontend_proof_cases_payload(self) -> dict[str, Any]:
        return self._payload_or_build("frontend_proof_cases_payload", self._build_frontend_proof_cases_payload)

    def _payload_or_build(self, page_name: str, builder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        if self.prefer_existing_payloads:
            try:
                return self.repository.get_page_payload(page_name)
            except FileNotFoundError:
                pass
        return builder()

    def _build_index_payload(self) -> dict[str, Any]:
        entities = self.repository.list_risk_entities()
        high_risk_count = int(_truthy_series(entities, "is_high_risk").sum()) if not entities.empty else 0
        return {
            "page_title": "workbench",
            "top_clues": entities.head(8).to_dict("records"),
            "hero": {
                "high_risk_entity_count": high_risk_count,
                "auto_dispatch_allowed": False,
            },
        }

    def _build_clues_payload(self) -> dict[str, Any]:
        entities = self.repository.list_risk_entities()
        return {"items": entities.to_dict("records"), "pagination": {"total_items": len(entities)}}

    def _build_frontend_workbench_payload(
        self,
        *,
        manufacturer_codes: list[str] | None,
        report_month: str | None,
        horizon: str | None,
        top_n: int | None,
    ) -> dict[str, Any]:
        rows = self._rankable_entity_items(
            manufacturer_codes=manufacturer_codes,
            report_month=report_month,
            horizon=horizon,
            candidate_type="recurring",
            top_n=top_n,
        )
        return {
            "batch_context": self._batch_context(),
            "overview_metrics": [
                {"label": "Workbench rows", "value": str(len(rows)), "tone": "neutral"},
                {"label": "Result-batch entities", "value": str(len(self.repository.list_risk_entities())), "tone": "neutral"},
            ],
            "model_metrics": [],
            "scope_policy": {
                "manufacturer_code_scope": "backend_resolved_scope",
                "returned_count": len(rows),
                "backend_may_request_top_n": True,
                "model_core_does_not_fill_user_worklists": True,
            },
            "rows": [_workbench_row(item) for item in rows],
            "meta": {
                "top_n_requested": top_n,
                "user_scope_resolved_by_backend": True,
                "model_core_filled_shortage": False,
            },
        }

    def _build_frontend_risk_entities_payload(
        self,
        *,
        manufacturer_codes: list[str] | None,
        report_month: str | None,
        horizon: str | None,
        top_n: int | None,
    ) -> dict[str, Any]:
        items = self._rankable_entity_items(
            manufacturer_codes=manufacturer_codes,
            report_month=report_month,
            horizon=horizon,
            candidate_type="recurring",
            top_n=top_n,
        )
        return {
            "batch_context": self._batch_context(),
            "entities": items,
            "pagination": {"total_items": len(items)},
            "meta": {
                "top_n_requested": top_n,
                "user_scope_resolved_by_backend": True,
                "model_core_filled_shortage": False,
            },
        }

    def _build_frontend_risk_entity_detail_payload(self, risk_entity_id: str) -> dict[str, Any]:
        row = self.repository.get_risk_entity(risk_entity_id)
        if row is None:
            raise KeyError(risk_entity_id)
        row_frame = _merge_entity_display_lookup(
            pd.DataFrame([row]),
            self.repository,
            str(row.get("report_month") or self.repository.manifest().report_month),
        )
        display_row = row_frame.iloc[0].to_dict() if not row_frame.empty else row
        item = _entity_item(pd.Series(display_row), self._card_counts(), self._primary_profile(row))
        profiles = self._horizon_profiles(risk_entity_id)
        return {"entity": item, "horizon_profiles": profiles}

    def _build_frontend_oneshot_payload(
        self,
        *,
        manufacturer_codes: list[str] | None,
        report_month: str | None,
        observation_date: str | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> dict[str, Any]:
        manifest = self.repository.manifest()
        declaration = manifest.raw.get("oneshot_terminals")
        if not isinstance(declaration, dict) or declaration.get("table_name") != "oneshot_terminals":
            return _oneshot_unavailable_payload(manifest, page=page, page_size=page_size)
        try:
            rows = self._oneshot_terminal_rows(manufacturer_codes=manufacturer_codes, report_month=report_month)
        except (FileNotFoundError, NotImplementedError, ValueError, AttributeError):
            return _oneshot_unavailable_payload(manifest, page=page, page_size=page_size)
        rows = _merge_entity_display_lookup(rows, self.repository, report_month or self.repository.manifest().report_month)
        rows = _sort_oneshot_facts(rows, sort_by=sort_by, sort_order=sort_order)
        total_rows = len(rows)
        total_pages = math.ceil(total_rows / page_size) if total_rows else 0
        start = (page - 1) * page_size
        rows = rows.iloc[start : start + page_size]
        items = []
        for _, row in rows.iterrows():
            first_purchase_date = _first_purchase_date(row)
            items.append(
                {
                    "oneshot_id": _text(row.get("oneshot_id")) or _text(row.get("risk_entity_id")) or _text(row.get("entity_id")),
                    "manufacturer_code": _text(row.get("manufacturer_code")),
                    "manufacturer_display_name": _display_name(
                        row, "manufacturer_display_name", "manufacturer_code", "Manufacturer"
                    ),
                    "manufacturer_name": _display_name(
                        row, "manufacturer_display_name", "manufacturer_code", "Manufacturer"
                    ),
                    "hospital_code": _text(row.get("hospital_code")),
                    "hospital_name": _display_name(row, "hospital_display_name", "hospital_code", "Hospital"),
                    "drug_group": _text(row.get("drug_group")),
                    "drug_name": _display_name(row, "drug_display_name", "drug_group", "Drug"),
                    "region": _text(row.get("region_display_name")) or _text(row.get("region_code")) or "Unknown region",
                    "first_purchase_date": first_purchase_date or "",
                    "first_purchase_amount": int(_number(row.get("first_purchase_amount"), 0)),
                    "days_since_first_purchase": int(_number(row.get("days_since_first_purchase"), 0)),
                }
            )
        return {
            "ready": True,
            "availability_status": "available",
            "report_month": manifest.report_month,
            "score_cutoff_date": manifest.score_cutoff_month,
            "result_batch_id": manifest.batch_id,
            "source_table": "oneshot_terminals",
            "source_schema_version": str(declaration.get("schema_version") or "oneshot_terminal_v1"),
            "summary": {"oneshot_count": total_rows},
            "items": items,
            "total": total_rows,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_rows,
                "total_pages": total_pages,
            },
            "sort": {"sort_by": sort_by, "sort_order": sort_order},
        }

    def _oneshot_terminal_rows(self, *, manufacturer_codes: list[str] | None, report_month: str | None) -> pd.DataFrame:
        rows = self.repository.load_table("oneshot_terminals")
        if not rows.empty:
            if manufacturer_codes is not None:
                rows = rows[rows["manufacturer_code"].astype(str).isin({str(code) for code in manufacturer_codes})]
            if report_month is not None and "report_month" in rows:
                rows = rows[rows["report_month"].astype(str).eq(str(report_month))]
        return rows.reset_index(drop=True)

    def _build_frontend_monthly_reports_payload(self) -> dict[str, Any]:
        reports = self.repository.list_monthly_reports()
        monthly_reports = []
        for _, row in reports.iterrows():
            monthly_reports.append(
                {
                    "monthly_report_id": str(row.get("monthly_report_id") or f"monthly_{self.repository.manifest().report_month}"),
                    "title": str(row.get("title") or f"{self.repository.manifest().report_month} monthly risk review"),
                    "report_month": str(row.get("report_month") or self.repository.manifest().report_month),
                    "score_batch_id": self._batch_context()["score_batch_id"],
                    "data_watermark_at": self._batch_context()["data_watermark_at"],
                    "summary": str(row.get("summary_text") or "Monthly risk review generated from the current result batch."),
                }
            )
        if not monthly_reports:
            monthly_reports.append(
                {
                    "monthly_report_id": f"monthly_{self.repository.manifest().report_month}",
                    "title": f"{self.repository.manifest().report_month} monthly risk review",
                    "report_month": self.repository.manifest().report_month,
                    "score_batch_id": self._batch_context()["score_batch_id"],
                    "data_watermark_at": self._batch_context()["data_watermark_at"],
                    "summary": "Monthly risk review generated from the current result batch.",
                }
            )
        return {
            "batch_context": self._batch_context(),
            "overview_metrics": [{"label": "Monthly reports", "value": str(len(monthly_reports)), "tone": "neutral"}],
            "model_metrics": [],
            "daily_report_options": [
                {
                    "daily_report_id": f"monthly_selector_{self.repository.manifest().report_month}",
                    "date": self.repository.manifest().score_cutoff_month,
                    "label": f"{self.repository.manifest().report_month} monthly batch",
                    "title": f"{self.repository.manifest().report_month} monthly risk review",
                    "report_month": self.repository.manifest().report_month,
                    "score_batch_id": self._batch_context()["score_batch_id"],
                    "data_watermark_at": self._batch_context()["data_watermark_at"],
                    "high_risk_entities": len(self.repository.list_rankable_entities(candidate_type="recurring")),
                    "oneshot_count": len(self.repository.list_rankable_entities(candidate_type="one_shot")),
                    "detector_alerts": len(self.repository.load_table("risk_cards")),
                    "summary": "Monthly batch selector for the current risk review.",
                }
            ],
            "monthly_reports": monthly_reports,
        }

    def _build_frontend_proof_cases_payload(self) -> dict[str, Any]:
        proof_cases = self.repository.list_proof_cases()
        items = []
        for _, row in proof_cases.iterrows():
            if not _text(row.get("proof_case_id")):
                continue
            items.append(
                {
                    "proof_case_id": str(row.get("proof_case_id")),
                    "title": str(row.get("title") or "Verified business case"),
                    "visible": str(row.get("visible") or "business"),
                    "outcome": str(row.get("outcome") or "verified"),
                    "case_summary": str(row.get("case_summary") or "Verified business result."),
                }
            )
        return {"items": items}

    def _rankable_entity_items(
        self,
        *,
        manufacturer_codes: list[str] | None,
        report_month: str | None,
        horizon: str | None,
        candidate_type: str,
        top_n: int | None,
    ) -> list[dict[str, Any]]:
        rows = self.repository.list_rankable_entities(
            manufacturer_codes=manufacturer_codes,
            report_month=report_month,
            horizon=horizon,
            candidate_type=candidate_type,
            sort_by=["business_priority_score_H", "business_priority_score", "risk_score_display", "risk_probability_value"],
            limit=top_n,
        )
        card_counts = self._card_counts()
        profiles = self.repository.load_table("risk_entity_horizon_profiles")
        return [_entity_item(row, card_counts, _matching_primary_profile(row, profiles)) for _, row in rows.iterrows()]

    def _batch_context(self) -> dict[str, Any]:
        manifest = self.repository.manifest()
        cutoff = manifest.score_cutoff_month
        return {
            "report_month": manifest.report_month,
            "score_as_of_date": cutoff,
            "data_watermark_at": f"{cutoff}T23:59:59+08:00",
            "score_batch_id": f"score_{manifest.report_month.replace('-', '')}_{manifest.primary_horizon.lower()}",
            "result_batch_id": manifest.batch_id,
            "primary_horizon": manifest.primary_horizon,
            "primary_horizon_label": f"{manifest.primary_horizon} window",
            "involved_amount_definition": "selected horizon window consumption from result-batch horizon profiles",
        }

    def _card_counts(self) -> dict[str, int]:
        cards = self.repository.load_table("risk_cards")
        if cards.empty or "risk_entity_id" not in cards:
            return {}
        return cards.groupby("risk_entity_id").size().to_dict()

    def _detector_results(self, risk_entity_id: str) -> list[dict[str, Any]]:
        cards = self.repository.list_risk_cards(risk_entity_id)
        evidence = self.repository.load_table("risk_card_evidence")
        if not evidence.empty and "risk_entity_id" in evidence:
            evidence = evidence[evidence["risk_entity_id"].astype(str).eq(str(risk_entity_id))]
        names = set(cards.get("source_detector_name", pd.Series(dtype=str)).dropna().astype(str))
        evidence_text = "\n".join(evidence.get("evidence_text", pd.Series(dtype=str)).dropna().astype(str).head(3).tolist())
        results = []
        for detector_id, detector_name, source_name in DETECTOR_TEMPLATES:
            if source_name and source_name in names:
                status = "hit"
                signal = "selected_evidence"
                score = 0.7
                text = evidence_text or "Selected evidence supports business review."
                action = "review_context"
            elif detector_id in {"delivery_time", "price_signal"}:
                status = "data_insufficient"
                signal = "not_customer_claim"
                score = 0.0
                text = "Source data is not sufficient for a customer-facing conclusion."
                action = "use_as_internal_context"
            elif detector_id in {"delivery_rate", "sku_wallet", "new_terminal"}:
                status = "not_applicable"
                signal = "not_applicable"
                score = 0.0
                text = "This detector is not applicable for the selected recurring entity."
                action = "no_action"
            else:
                status = "stable"
                signal = "not_hit"
                score = 0.0
                text = "No selected business-visible evidence in the current monthly batch."
                action = "monitor"
            results.append(
                {
                    "detector_id": detector_id,
                    "detector_name": detector_name,
                    "score": score,
                    "signal": signal,
                    "status": status,
                    "evidence": text,
                    "action": action,
                }
            )
        return results

    def _primary_profile(self, row: dict[str, Any]) -> dict[str, Any] | None:
        profiles = self.repository.list_risk_entity_horizon_profiles(
            risk_entity_id=str(row.get("risk_entity_id")),
            horizon=str(row.get("primary_horizon", row.get("horizon", ""))),
        )
        if profiles.empty:
            return None
        return profiles.iloc[0].to_dict()

    def _horizon_profiles(self, risk_entity_id: str) -> dict[str, dict[str, Any]]:
        profile_rows = self.repository.list_risk_entity_horizon_profiles(risk_entity_id=risk_entity_id)
        detector_results = self._detector_results(risk_entity_id)
        if not profile_rows.empty:
            profiles: dict[str, dict[str, Any]] = {}
            for _, row in profile_rows.iterrows():
                horizon = str(row["horizon"])
                profiles[horizon] = {
                    "horizon": horizon,
                    "label": f"{horizon} window",
                    "risk_probability": _json_value(row.get("risk_probability")),
                    "involved_amount": int(_number(row.get("involved_amount"), 0)),
                    "involved_amount_source": _text(row.get("involved_amount_source")),
                    "risk_level": _text(row.get("risk_level")),
                    "risk_band": _text(row.get("risk_band")),
                    "main_reason_summary": _safe_reason(row.get("main_reason_summary") or row.get("reason")),
                    "reason": _safe_reason(row.get("reason") or row.get("main_reason_summary")),
                    "detector_evidence_count": int(_number(row.get("detector_evidence_count"), 0)),
                    "updated_at": _text(row.get("updated_at")),
                    "detector_results": detector_results,
                    "xgboost_shap": [],
                    "detector_narrative": "Risk review is supported by result-batch evidence and purchasing rhythm context.",
                }
            return profiles

        item = _entity_item(pd.Series(self.repository.get_risk_entity(risk_entity_id) or {}), self._card_counts())
        profiles = {}
        for horizon, label in [("H3", "3-month window"), ("H6", "6-month window"), ("H12", "12-month window")]:
            profiles[horizon] = {
                "horizon": horizon,
                "label": label,
                "risk_probability": item["risk_probability"],
                "involved_amount": item.get("involved_amount", item.get("average_consumption_in_window", 0)),
                "involved_amount_source": "legacy_risk_entities_row",
                "risk_level": item.get("risk_band", ""),
                "risk_band": item.get("risk_band", ""),
                "main_reason_summary": f"{label}: review selected result-batch evidence.",
                "reason": f"{label}: review selected result-batch evidence.",
                "detector_evidence_count": 0,
                "detector_results": detector_results,
                "xgboost_shap": [],
                "detector_narrative": "Risk review is supported by result-batch evidence and purchasing rhythm context.",
            }
        return profiles

    def _dashboard_metrics(self) -> dict[str, Any]:
        entities = self.repository.list_risk_entities()
        return {
            "risk_entity_count": int(len(entities)),
            "auto_dispatch_allowed": False,
            "customer_facing_probability_service_allowed": False,
        }


def _entity_item(row: pd.Series, card_counts: dict[str, int], horizon_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    entity_id = str(row["risk_entity_id"])
    profile = horizon_profile or {}
    probability = _probability(profile.get("risk_probability")) if not _is_missing(profile.get("risk_probability")) else _entity_probability(row)
    involved_amount = int(_number(profile.get("involved_amount"), _average_consumption(row)))
    involved_amount_source = _text(profile.get("involved_amount_source")) or "risk_entities_legacy_amount"
    item = {
        "entity_id": entity_id,
        "hospital_name": _display_name(row, "hospital_display_name", "hospital_code", "Hospital"),
        "drug_name": _display_name(row, "drug_display_name", "drug_group", "Drug"),
        "manufacturer_code": str(row.get("manufacturer_code", "unknown")),
        "manufacturer_display_name": _display_name(row, "manufacturer_display_name", "manufacturer_code", "Manufacturer"),
        "manufacturer_name": _display_name(row, "manufacturer_display_name", "manufacturer_code", "Manufacturer"),
        "region": _text(row.get("region_display_name")) or _text(row.get("region_code")) or "Unknown region",
        "horizon": _text(profile.get("horizon")) or str(row.get("primary_horizon", row.get("horizon", "H6"))),
        "risk_probability": probability,
        "involved_amount": involved_amount,
        "involved_amount_source": involved_amount_source,
        "average_consumption_in_window": involved_amount,
        "risk_band": _text(profile.get("risk_band")) or _risk_band(row),
        "risk_color": _risk_color(row),
        "last_purchase_date": _text(row.get("last_purchase_date")) or "unknown",
        "days_since_last_purchase": int(_number(row.get("days_since_last_purchase"), 0)),
        "risk_card_count": int(card_counts.get(entity_id, row.get("risk_card_count", 0) or 0)),
        "status": _status_label(row),
        "monthly_status": _text(row.get("monthly_status")) or "current_month_selected",
        "value_level": _text(row.get("potential_value_level")) or "unknown",
        "main_reason_summary": _safe_reason(profile.get("main_reason_summary") or profile.get("reason") or row.get("main_reason_summary")),
        "primary_reason": _safe_reason(profile.get("reason") or profile.get("main_reason_summary") or row.get("risk_type_label") or row.get("main_reason_summary")),
    }
    for field in OPTIONAL_RANKING_FIELDS:
        if field in row.index and not _is_missing(row.get(field)):
            item[field] = _json_value(row.get(field))
    return item


def _workbench_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_id": item["entity_id"],
        "entity_id": item["entity_id"],
        "manufacturer_code": item["manufacturer_code"],
        "hospital_name": item["hospital_name"],
        "drug_name": item["drug_name"],
        "region": item["region"],
        "risk_probability": item["risk_probability"],
        "involved_amount": item["involved_amount"],
        "involved_amount_source": item["involved_amount_source"],
        "average_consumption_in_window": item["average_consumption_in_window"],
        "source_type": "result_batch",
        "fill_source": "backend_scope_query",
        "action": "view_detail",
    }


def _merge_entity_display_lookup(rows: pd.DataFrame, repository: RiskResultRepository, report_month: str) -> pd.DataFrame:
    if rows.empty:
        return rows
    try:
        lookup = repository.load_entity_display_lookup(report_month=report_month)
    except (FileNotFoundError, NotImplementedError, ValueError, AttributeError):
        return rows
    join_cols = ["tenant_id", "report_month", "manufacturer_code", "hospital_code", "drug_group"]
    if lookup.empty or not set(join_cols).issubset(rows.columns) or not set(join_cols).issubset(lookup.columns):
        return rows
    display_cols = [
        "manufacturer_display_name",
        "hospital_display_name",
        "drug_display_name",
        "region_code",
        "region_display_name",
        "product_line_code",
        "product_line_name",
    ]
    available = [col for col in display_cols if col in lookup.columns]
    joined = rows.merge(
        lookup[join_cols + available].drop_duplicates(join_cols, keep="first"),
        on=join_cols,
        how="left",
        suffixes=("", "_lookup"),
    )
    for col in available:
        lookup_col = f"{col}_lookup"
        if lookup_col not in joined.columns:
            continue
        lookup_values = joined[lookup_col].map(_text)
        current_values = joined[col].map(_text) if col in joined else pd.Series("", index=joined.index)
        joined[col] = lookup_values.where(lookup_values.str.len().gt(0), current_values)
        joined = joined.drop(columns=[lookup_col])
    return joined


def _sort_oneshot_facts(rows: pd.DataFrame, *, sort_by: str, sort_order: str) -> pd.DataFrame:
    if rows.empty:
        return rows.reset_index(drop=True)
    allowed = {"first_purchase_date", "first_purchase_amount", "days_since_first_purchase"}
    if sort_by not in allowed:
        raise ValueError(f"Unsupported One-shot fact sort: {sort_by}")
    if sort_order not in {"asc", "desc"}:
        raise ValueError(f"Unsupported One-shot sort order: {sort_order}")
    sortable = rows.copy()
    if sort_by == "first_purchase_date":
        sortable["__oneshot_sort_value"] = pd.to_datetime(sortable.get(sort_by), errors="coerce")
    else:
        sortable["__oneshot_sort_value"] = pd.to_numeric(sortable.get(sort_by), errors="coerce")
    by = ["__oneshot_sort_value"]
    ascending = [sort_order == "asc"]
    if "oneshot_id" in sortable:
        by.append("oneshot_id")
        ascending.append(True)
    return (
        sortable.sort_values(by, ascending=ascending, na_position="last", kind="mergesort")
        .drop(columns=["__oneshot_sort_value"])
        .reset_index(drop=True)
    )


def _oneshot_unavailable_payload(manifest: Any, *, page: int, page_size: int) -> dict[str, Any]:
    return {
        "ready": False,
        "availability_status": "unavailable",
        "error_code": "ONESHOT_RESULT_NOT_AVAILABLE",
        "message": "The current formal batch has not published One-shot terminal facts.",
        "report_month": manifest.report_month,
        "score_cutoff_date": manifest.score_cutoff_month,
        "result_batch_id": manifest.batch_id,
        "source_table": "oneshot_terminals",
        "summary": {"oneshot_count": 0},
        "items": [],
        "total": 0,
        "pagination": {"page": page, "page_size": page_size, "total": 0, "total_pages": 0},
    }


def _matching_primary_profile(row: pd.Series, profiles: pd.DataFrame) -> dict[str, Any] | None:
    if profiles.empty or "risk_entity_id" not in profiles:
        return None
    risk_entity_id = str(row.get("risk_entity_id"))
    horizon = str(row.get("primary_horizon", row.get("horizon", "")))
    matches = profiles[profiles["risk_entity_id"].astype(str).eq(risk_entity_id)]
    if horizon and "horizon" in matches:
        primary = matches[matches["horizon"].astype(str).eq(horizon)]
        if not primary.empty:
            return primary.iloc[0].to_dict()
    if not matches.empty:
        return matches.iloc[0].to_dict()
    return None


def _oneshot_summary(rows: pd.DataFrame, observation_date: str | None, fallback_date: str | None) -> dict[str, int]:
    observation_day = _parse_date(observation_date) or _parse_date(fallback_date)
    if observation_day is None or rows.empty:
        return {"daily_new_terminal_count": 0, "monthly_new_terminal_count": 0}
    month_start = observation_day.replace(day=1)
    dates = [_parse_date(_first_purchase_date(row)) for _, row in rows.iterrows()]
    valid_dates = [date for date in dates if date is not None]
    return {
        "daily_new_terminal_count": sum(1 for date in valid_dates if date == observation_day),
        "monthly_new_terminal_count": sum(1 for date in valid_dates if month_start <= date <= observation_day),
    }


def _first_purchase_date(row: pd.Series | dict[str, Any]) -> str | None:
    for field in [
        "first_purchase_date",
        "first_purchase_time",
        "first_order_date",
        "first_seen_date",
        "purchase_time_min",
        "first_purchase_month_asof_cutoff",
        "first_purchase_month",
    ]:
        text = _text(row.get(field))
        parsed = _parse_date(text)
        if parsed is not None:
            return parsed.isoformat()
    return None


def _parse_date(value: Any) -> Any | None:
    if _is_missing(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _days_between(first_purchase_date: str | None, observation_day: Any | None) -> int:
    first_day = _parse_date(first_purchase_date)
    if first_day is None or observation_day is None:
        return 0
    return max((observation_day - first_day).days, 0)


def _entity_probability(row: pd.Series) -> float:
    for field in ["risk_probability_value", "churn_probability_H", "risk_probability", "risk_score_display", "risk_score"]:
        if field in row.index and not _is_missing(row.get(field)):
            return _probability(row.get(field))
    return 0.0


def _average_consumption(row: pd.Series) -> int:
    for field in ["average_consumption_in_window", "value_at_risk_H", "value_at_risk_proxy", "recent_order_amount", "avg_order_amount"]:
        if field in row.index and not _is_missing(row.get(field)):
            return int(max(_number(row.get(field), 0), 0))
    return 0


def _risk_color(row: pd.Series) -> str:
    color = str(row.get("risk_color") or row.get("risk_level") or "").lower()
    if color in {"red", "orange", "yellow", "gray"}:
        return color
    if str(row.get("risk_level", "")).lower() == "high":
        return "red"
    return "gray"


def _risk_band(row: pd.Series) -> str:
    if _truthy(row.get("is_observation")) or str(row.get("final_candidate_status", "")).lower() == "observation_only":
        return "Observation"
    return {"red": "High risk", "orange": "Medium risk", "yellow": "Observation", "gray": "Data insufficient"}[_risk_color(row)]


def _status_label(row: pd.Series) -> str:
    status = str(row.get("final_candidate_status") or row.get("review_status") or "").lower()
    if "priority" in status:
        return "follow_up"
    if "manual" in status:
        return "confirm"
    if "observation" in status:
        return "observe"
    if "one_shot" in status:
        return "new_terminal"
    return "review"


def _display_name(row: pd.Series, display_col: str, code_col: str, prefix: str) -> str:
    display = _text(row.get(display_col))
    if display:
        return display
    code = _text(row.get(code_col)) or "unknown"
    return f"{prefix}_{code}"


def _safe_reason(value: Any) -> str:
    text = _text(value)
    if not text or text == "multi_recall_union_top10":
        return "Selected by the current monthly risk worklist policy."
    return text.replace("multi_recall_union_top10", "monthly_risk_worklist")


def _probability(value: Any) -> float:
    return round(min(1.0, max(0.0, _number(value, 0.0))), 6)


def _number(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number):
        return default
    return number


def _text(value: Any) -> str:
    if _is_missing(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none"} else text


def _truthy(value: Any) -> bool:
    if _is_missing(value):
        return False
    return str(value).lower() in {"true", "1", "yes", "y"}


def _truthy_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df:
        return pd.Series(False, index=df.index)
    return df[column].astype(str).str.lower().isin({"true", "1", "yes", "y"})


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value)) or pd.isna(value)


def _json_value(value: Any) -> Any:
    if _is_missing(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value
