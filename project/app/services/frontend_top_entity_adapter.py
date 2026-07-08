from __future__ import annotations

from typing import Any

from app.services.user_top_entity_service import TopEntityService


def build_risk_entities_payload_from_top_entities(
    service: TopEntityService,
    *,
    user_id: str,
    top_n: int = 20,
    horizon: str = "H6",
) -> dict[str, Any] | None:
    top_entities = service.list_user_top_entities(
        user_id=user_id,
        horizon=horizon,
        top_n=top_n,
        group_by="user_scope",
        ranking_strategy="probability",
        candidate_type="recurring",
        fill_policy="none",
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
        "score_formula": f"ranking_strategy={top_entities.get('ranking_strategy_effective') or 'probability'}",
    }


def _risk_entity_item(entity: dict[str, Any], top_entities: dict[str, Any]) -> dict[str, Any]:
    probability = _clamped_probability(entity.get("risk_probability"))
    average_consumption = _int_or_zero(entity.get("average_consumption_in_window"))
    return {
        "entity_id": _text(entity.get("risk_entity_id") or entity.get("candidate_id")),
        "hospital_name": _text(entity.get("hospital_display_name") or entity.get("hospital_code")),
        "drug_name": _text(entity.get("drug_display_name") or entity.get("drug_code")),
        "manufacturer_code": _text(entity.get("manufacturer_code")),
        "region": _text(entity.get("region_display_name")),
        "horizon": _text(entity.get("horizon") or top_entities.get("horizon") or "H6"),
        "risk_probability": probability,
        "average_consumption_in_window": average_consumption,
        "business_score": round(probability * average_consumption),
        "risk_band": _text(entity.get("risk_level") or entity.get("candidate_type")),
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
