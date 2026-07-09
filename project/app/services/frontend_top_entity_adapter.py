from __future__ import annotations

from typing import Any

from app.services.user_top_entity_service import TopEntityService


def build_risk_entities_payload_from_top_entities(
    service: TopEntityService,
    *,
    user_id: str,
    top_n: int = 20,
    horizon: str = "H6",
    report_month: str | None = None,
    manufacturer_codes: list[str] | None = None,
    sort_by: str = "risk_probability",
) -> dict[str, Any] | None:
    top_entities = service.list_user_top_entities(
        user_id=user_id,
        report_month=report_month,
        horizon=horizon,
        top_n=top_n,
        group_by="user_scope",
        ranking_strategy=_ranking_strategy(sort_by),
        candidate_type="recurring",
        fill_policy="none",
        manufacturer_codes=manufacturer_codes,
    )
    entities = [
        entity for group in top_entities.get("groups", []) for entity in group.get("entities", [])
    ]
    if not entities:
        return None

    items = [_risk_entity_item(entity, top_entities) for entity in entities]
    return {
        "batch_context": _batch_context(top_entities),
        "entities": items,
        "pagination": {
            "page": 1,
            "page_size": len(items),
            "total": len(items),
        },
        "scope": top_entities.get("scope", {}),
        "query": _query(top_entities, sort_by),
        "current_user_id": top_entities.get("user_id"),
        "warnings": list(top_entities.get("warnings") or []),
    }


def build_workbench_payload_from_top_entities(
    service: TopEntityService,
    *,
    user_id: str,
    top_n: int = 20,
    horizon: str = "H6",
    report_month: str | None = None,
    manufacturer_codes: list[str] | None = None,
    sort_by: str = "risk_probability",
    detector_summary: dict[str, Any] | None = None,
    run_date: str | None = None,
) -> dict[str, Any] | None:
    risk_entities_payload = build_risk_entities_payload_from_top_entities(
        service,
        user_id=user_id,
        top_n=top_n,
        horizon=horizon,
        report_month=report_month,
        manufacturer_codes=manufacturer_codes,
        sort_by=sort_by,
    )
    if not risk_entities_payload:
        return None
    rows = [_workbench_row(item) for item in risk_entities_payload["entities"]]
    summary = detector_summary or {
        "detector_clue_count": 0,
        "highest_detector_score": None,
        "latest_detector_run_date": run_date,
        "top_clues": [],
        "detector_status_summary": "not_requested",
    }
    query = risk_entities_payload.get("query", {})
    scope = risk_entities_payload.get("scope", {})
    current_manufacturer = _current_manufacturer(scope)
    return {
        "ready": True,
        "data_source": "risk_model_core",
        "demo_mode": False,
        "batch_context": risk_entities_payload["batch_context"],
        "overview_metrics": [
            {"label": "monthly_risk_entity_count", "value": str(len(rows)), "tone": "neutral"},
        ],
        "rows": rows,
        "scope": scope,
        "query": query,
        "detector_summary": summary,
        "current_user_id": risk_entities_payload.get("current_user_id"),
        "current_manufacturer_code": current_manufacturer,
        "current_observation_date": run_date or summary.get("latest_detector_run_date"),
        "horizon": query.get("horizon", "H6"),
        "top_n": int(query.get("top_n") or len(rows)),
        "sort_by": query.get("sort_by", sort_by),
        "today_clue_count": int(summary.get("detector_clue_count") or 0),
        "highest_detector_score": summary.get("highest_detector_score"),
        "priority_risk_entity_count": len(rows),
        "today_high_score_rule_clues": list(summary.get("top_clues") or [])[:5],
        "monthly_risk_entities": rows,
        "warnings": list(risk_entities_payload.get("warnings") or []),
    }


def _batch_context(top_entities: dict[str, Any]) -> dict[str, str]:
    report_month = str(top_entities.get("report_month") or "latest")
    horizon = str(top_entities.get("horizon") or "H6")
    return {
        "report_month": report_month,
        "score_as_of_date": report_month,
        "data_watermark_at": report_month,
        "score_batch_id": "top_entity_service",
        "result_batch_id": "risk_result_batch",
        "primary_horizon": horizon,
        "primary_horizon_label": horizon,
        "involved_amount_definition": "selected horizon window consumption",
    }


def _risk_entity_item(entity: dict[str, Any], top_entities: dict[str, Any]) -> dict[str, Any]:
    probability = _clamped_probability(entity.get("risk_probability"))
    involved_amount = _int_or_zero(entity.get("involved_amount"))
    return {
        "entity_id": _text(entity.get("risk_entity_id") or entity.get("candidate_id")),
        "hospital_name": _text(entity.get("hospital_display_name") or entity.get("hospital_code")),
        "drug_name": _text(entity.get("drug_display_name") or entity.get("drug_code")),
        "manufacturer_code": _text(entity.get("manufacturer_code")),
        "region": _text(entity.get("region_display_name")),
        "horizon": _text(entity.get("horizon") or top_entities.get("horizon") or "H6"),
        "risk_probability": probability,
        "loss_value": _int_or_zero(entity.get("loss_value")),
        "loss_value_status": _text(entity.get("loss_value_status") or "amount_proxy_missing"),
        "sort_policy": _text(entity.get("sort_policy") or "risk_probability_desc_due_to_missing_amount_proxy"),
        "involved_amount": involved_amount,
        "involved_amount_source": _text(entity.get("involved_amount_source")),
        "average_consumption_in_window": involved_amount,
        "risk_band": _text(entity.get("risk_band") or entity.get("risk_level") or entity.get("candidate_type")),
        "risk_color": _text(entity.get("risk_color") or "gray"),
        "last_purchase_date": _text(
            entity.get("last_purchase_date") or top_entities.get("report_month")
        ),
        "days_since_last_purchase": _int_or_zero(entity.get("days_since_last_purchase")),
        "risk_card_count": _int_or_zero(entity.get("risk_card_count")),
        "status": _text(entity.get("review_status") or entity.get("candidate_type")),
        "monthly_status": _text(
            entity.get("final_candidate_status") or entity.get("candidate_type")
        ),
        "value_level": _text(entity.get("review_priority") or entity.get("risk_level")),
        "primary_reason": _text(
            entity.get("main_reason_summary") or entity.get("suggested_action_short")
        ),
    }


def _workbench_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_id": item["entity_id"],
        "entity_id": item["entity_id"],
        "manufacturer_code": item["manufacturer_code"],
        "hospital_name": item["hospital_name"],
        "drug_name": item["drug_name"],
        "region": item["region"],
        "horizon": item["horizon"],
        "risk_probability": item["risk_probability"],
        "loss_value": item["loss_value"],
        "loss_value_status": item["loss_value_status"],
        "sort_policy": item["sort_policy"],
        "involved_amount": item["involved_amount"],
        "involved_amount_source": item["involved_amount_source"],
        "average_consumption_in_window": item["average_consumption_in_window"],
        "risk_band": item["risk_band"],
        "source_type": "risk_result_batch",
        "action": "view_detail",
    }


def _query(top_entities: dict[str, Any], sort_by: str) -> dict[str, Any]:
    return {
        "report_month": top_entities.get("report_month"),
        "horizon": top_entities.get("horizon"),
        "top_n": top_entities.get("top_n"),
        "sort_by": sort_by,
    }


def _ranking_strategy(sort_by: str) -> str:
    if sort_by == "loss_value":
        return "loss_value"
    if sort_by == "detector_score":
        return "detector_score"
    if sort_by == "involved_amount":
        return "involved_amount"
    return "probability"


def _current_manufacturer(scope: dict[str, Any]) -> str | None:
    codes = scope.get("manufacturer_codes") or []
    return str(codes[0]) if codes else None


def _clamped_probability(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, numeric))


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
