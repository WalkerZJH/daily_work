from __future__ import annotations

from typing import Any


def build_default_frontend_payloads() -> dict[str, Any]:
    entities = [_risk_entity(index) for index in range(20)]
    details = {item["entity_id"]: _risk_entity_detail(item) for item in entities}
    return {
        "workbench": _workbench_payload(entities),
        "risk_entities": {
            "batch_context": _batch_context(),
            "entities": entities,
            "pagination": {"page": 1, "page_size": len(entities), "total": len(entities)},
        },
        "risk_entity_details": details,
        "oneshot_terminals": _oneshot_payload(),
        "monthly_reports": _monthly_reports_payload(),
        "proof_cases": {"items": []},
    }


def _batch_context() -> dict[str, str]:
    return {
        "report_month": "2025-12",
        "score_as_of_date": "2025-12-31",
        "data_watermark_at": "2025-12-31T23:59:59+08:00",
        "score_batch_id": "default_score_202512_h6",
        "result_batch_id": "default_frontend_payload",
        "primary_horizon": "H6",
        "primary_horizon_label": "H6 window",
        "score_formula": "risk_probability * average_consumption_in_window",
    }


def _risk_entity(index: int) -> dict[str, Any]:
    probability = round(0.95 - index * 0.02, 4)
    average = 1000 - index * 25
    return {
        "entity_id": f"entity_{index + 1:02d}",
        "hospital_name": f"Hospital {index + 1:02d}",
        "drug_name": f"Drug {index + 1:02d}",
        "manufacturer_code": f"M{(index % 4) + 1}",
        "region": "default-region",
        "horizon": "H6",
        "risk_probability": probability,
        "average_consumption_in_window": average,
        "business_score": round(probability * average),
        "risk_band": "High risk" if index < 5 else "Medium risk",
        "risk_color": "red" if index < 5 else "orange",
        "last_purchase_date": "2025-12-15",
        "days_since_last_purchase": 16 + index,
        "risk_card_count": 2,
        "status": "follow_up",
        "monthly_status": "current_month_selected",
        "value_level": "high",
        "primary_reason": "Selected by the current monthly risk worklist policy.",
    }


def _workbench_payload(entities: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        {
            "row_id": item["entity_id"],
            "entity_id": item["entity_id"],
            "manufacturer_code": item["manufacturer_code"],
            "hospital_name": item["hospital_name"],
            "drug_name": item["drug_name"],
            "region": item["region"],
            "risk_probability": item["risk_probability"],
            "average_consumption_in_window": item["average_consumption_in_window"],
            "business_score": item["business_score"],
            "source_type": "default_payload",
            "fill_source": "default_payload",
            "action": "view_detail",
        }
        for item in entities
    ]
    return {
        "batch_context": _batch_context(),
        "overview_metrics": [
            {"label": "Workbench rows", "value": str(len(rows)), "tone": "neutral"},
        ],
        "model_metrics": [],
        "fill_policy": {
            "manufacturer_code": "backend_resolved_scope",
            "workbench_target_count": len(rows),
            "global_current_month_hospital_drug_count": len(rows),
            "fill_reason": "Default payload for local API smoke tests.",
        },
        "rows": rows,
    }


def _risk_entity_detail(entity: dict[str, Any]) -> dict[str, Any]:
    profiles = {}
    for horizon in ["H3", "H6", "H12"]:
        profiles[horizon] = {
            "horizon": horizon,
            "label": f"{horizon} window",
            "risk_probability": entity["risk_probability"],
            "average_consumption_in_window": entity["average_consumption_in_window"],
            "business_score": entity["business_score"],
            "reason": "Review selected result-batch evidence.",
            "detector_results": [
                {
                    "detector_id": "purchase_gap",
                    "detector_name": "Purchase gap",
                    "score": 0.7,
                    "signal": "selected_evidence",
                    "status": "hit",
                    "evidence": "Monthly evidence supports business review.",
                    "action": "review_context",
                }
            ],
            "xgboost_shap": [
                {
                    "feature": "risk_probability_value",
                    "contribution": 0.12,
                    "explanation": "Probability contributes to worklist rank.",
                }
            ],
            "detector_narrative": "Risk review is supported by result-batch evidence.",
        }
    return {"entity": entity, "horizon_profiles": profiles}


def _oneshot_payload() -> dict[str, Any]:
    items = [
        {
            "oneshot_id": "oneshot_01",
            "hospital_name": "Hospital New 01",
            "drug_name": "Drug New 01",
            "region": "default-region",
            "first_purchase_date": "2025-12-01",
            "first_purchase_amount": 1200,
            "days_since_first_purchase": 30,
        }
    ]
    return {
        "ready": True,
        "availability_status": "demo",
        "report_month": "2025-12",
        "score_cutoff_date": "2025-12-31",
        "result_batch_id": "demo-oneshot-facts",
        "source_table": "demo",
        "summary": {"oneshot_count": len(items)},
        "items": items,
        "total": len(items),
        "pagination": {"page": 1, "page_size": 50, "total": len(items), "total_pages": 1},
        "sort": {"sort_by": "first_purchase_date", "sort_order": "desc"},
    }


def _monthly_reports_payload() -> dict[str, Any]:
    return {
        "batch_context": _batch_context(),
        "overview_metrics": [{"label": "Monthly reports", "value": "1", "tone": "neutral"}],
        "model_metrics": [],
        "daily_report_options": [
            {
                "daily_report_id": "daily_2025_12_31",
                "date": "2025-12-31",
                "label": "2025-12 monthly batch",
                "title": "2025-12 monthly risk review",
                "report_month": "2025-12",
                "score_batch_id": "default_score_202512_h6",
                "data_watermark_at": "2025-12-31T23:59:59+08:00",
                "high_risk_entities": 5,
                "oneshot_count": 1,
                "detector_alerts": 2,
                "summary": "Monthly batch selector for the current risk review.",
            }
        ],
        "monthly_reports": [
            {
                "monthly_report_id": "monthly_2025_12",
                "title": "2025-12 monthly risk review",
                "report_month": "2025-12",
                "score_batch_id": "default_score_202512_h6",
                "data_watermark_at": "2025-12-31T23:59:59+08:00",
                "summary": "Monthly risk review generated from the default payload.",
            }
        ],
    }
