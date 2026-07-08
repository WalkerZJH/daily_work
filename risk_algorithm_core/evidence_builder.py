"""Build bounded RiskCard and RiskEvidence tables from selected candidates and detectors."""

from __future__ import annotations

import pandas as pd


FORBIDDEN_CLAIMS_TEXT = "No definitive churn, competitor replacement, policy loss, distributor responsibility, or auto dispatch claim."


def build_risk_cards(candidate_status: pd.DataFrame, detector_outputs: pd.DataFrame) -> pd.DataFrame:
    cards = []
    for row in candidate_status.itertuples():
        risk_entity_id = str(row.candidate_id)
        cards.append(
            {
                "risk_card_id": f"card_primary_{row.candidate_id}",
                "risk_entity_id": risk_entity_id,
                "candidate_id": row.candidate_id,
                "card_type": _primary_card_type(row.candidate_type),
                "card_title": _card_title(row.candidate_type),
                "card_level": row.risk_level,
                "card_color": row.risk_color,
                "horizon": row.horizon,
                "risk_probability_display": "hidden" if row.is_one_shot or row.is_observation else "risk band",
                "card_summary": _card_summary(row.candidate_type),
                "candidate_reason": row.selection_reason,
                "is_primary": True,
                "source_module": "risk_algorithm_core",
                "evidence_count": 0,
                "suggested_action": _suggested_action(row.candidate_type),
                "user_visible_caveat": _caveat(row.candidate_type),
                "created_at": row.cutoff_month,
            }
        )
        hit_detectors = detector_outputs[(detector_outputs["candidate_id"].astype(str) == str(row.candidate_id)) & detector_outputs["hit_flag"].fillna(False)]
        for detector in hit_detectors.head(4).itertuples():
            cards.append(
                {
                    "risk_card_id": f"card_{detector.detector_name}_{row.candidate_id}",
                    "risk_entity_id": risk_entity_id,
                    "candidate_id": row.candidate_id,
                    "card_type": str(detector.evidence_type),
                    "card_title": _detector_title(str(detector.detector_name)),
                    "card_level": row.risk_level,
                    "card_color": row.risk_color,
                    "horizon": row.horizon,
                    "risk_probability_display": "hidden" if row.is_one_shot or row.is_observation else "risk band",
                    "card_summary": _detector_summary(str(detector.detector_name)),
                    "candidate_reason": str(detector.reason_code),
                    "is_primary": False,
                    "source_module": "detector",
                    "source_detector_name": str(detector.detector_name),
                    "evidence_count": 0,
                    "suggested_action": _suggested_action(row.candidate_type),
                    "user_visible_caveat": str(detector.caveat),
                    "created_at": row.cutoff_month,
                }
            )
    cards_df = pd.DataFrame(cards)
    if cards_df.empty:
        return cards_df
    cards_df["risk_card_count"] = cards_df.groupby("risk_entity_id")["risk_card_id"].transform("count")
    return cards_df.groupby("risk_entity_id", group_keys=False).head(5).reset_index(drop=True)


def build_risk_card_evidence(risk_cards: pd.DataFrame, detector_outputs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if risk_cards.empty:
        return pd.DataFrame(columns=["evidence_id", "risk_card_id", "risk_entity_id", "candidate_id", "evidence_type", "evidence_text", "business_metric_name", "business_metric_value", "source_feature_name", "source_feature_value", "visibility_level", "sort_order"])
    for card in risk_cards.itertuples():
        if bool(getattr(card, "is_primary", False)):
            rows.append(_evidence_row(card, "selection_reason", str(card.card_summary), "", "", 1))
            continue
        detector_name = getattr(card, "source_detector_name", "")
        det = detector_outputs[
            (detector_outputs["candidate_id"].astype(str) == str(card.candidate_id))
            & detector_outputs["hit_flag"].fillna(False)
            & detector_outputs["detector_name"].astype(str).eq(str(detector_name))
        ]
        if det.empty:
            rows.append(_evidence_row(card, "detector_note", str(card.card_summary), "", "", 1))
            continue
        for idx, row in enumerate(det.head(3).itertuples(), start=1):
            rows.append(
                _evidence_row(
                    card,
                    str(row.evidence_type),
                    _evidence_text(str(row.detector_name)),
                    str(row.metric_name),
                    row.metric_value,
                    idx,
                )
            )
    return pd.DataFrame(rows)


def _evidence_row(card: object, evidence_type: str, text: str, metric_name: str, metric_value: object, sort_order: int) -> dict:
    return {
        "evidence_id": f"ev_{sort_order}_{card.risk_card_id}",
        "risk_card_id": card.risk_card_id,
        "risk_entity_id": card.risk_entity_id,
        "candidate_id": card.candidate_id,
        "evidence_type": evidence_type,
        "evidence_level": "business_visible",
        "evidence_text": text,
        "business_metric_name": metric_name,
        "business_metric_value": metric_value,
        "source_feature_name": metric_name,
        "source_feature_value": metric_value,
        "visibility_level": "business_visible",
        "sort_order": sort_order,
    }


def _primary_card_type(candidate_type: str) -> str:
    return {
        "recurring": "primary_risk",
        "one_shot": "one_shot_attention",
        "observation": "demand_shape_observation",
        "demand_shape_observation": "demand_shape_observation",
    }.get(candidate_type, "primary_risk")


def _card_title(candidate_type: str) -> str:
    return {
        "recurring": "Monthly risk review",
        "one_shot": "New terminal attention",
        "observation": "Observation item",
        "demand_shape_observation": "Observation item",
    }.get(candidate_type, "Monthly risk review")


def _card_summary(candidate_type: str) -> str:
    return {
        "recurring": "Selected for monthly purchasing risk review.",
        "one_shot": "Selected as a new terminal attention item; not recurring churn.",
        "observation": "Selected for observation; not a strong warning.",
        "demand_shape_observation": "Selected for observation; not a strong warning.",
    }.get(candidate_type, "Selected for monthly review.")


def _suggested_action(candidate_type: str) -> str:
    return {
        "recurring": "Review recent purchasing plans and demand context.",
        "one_shot": "Check whether a second purchase can be encouraged.",
        "observation": "Continue monitoring without treating it as high risk.",
        "demand_shape_observation": "Continue monitoring without treating it as high risk.",
    }.get(candidate_type, "Manual review recommended.")


def _caveat(candidate_type: str) -> str:
    return {
        "recurring": "Risk clue requires business verification.",
        "one_shot": "New terminal attention is not recurring churn probability.",
        "observation": "Observation item is not high risk.",
        "demand_shape_observation": "Observation item is not high risk.",
    }.get(candidate_type, "Business review required.")


def _detector_title(detector_name: str) -> str:
    titles = {
        "purchase_interval_overdue_warning": "Purchase interval evidence",
        "purchase_frequency_fluctuation_warning": "Frequency drop evidence",
        "purchase_quantity_fluctuation_warning": "Quantity change evidence",
        "terminal_loss_warning": "Monthly risk evidence",
        "new_terminal_detection": "New terminal fact",
    }
    return titles.get(detector_name, "Business evidence")


def _detector_summary(detector_name: str) -> str:
    return {
        "purchase_interval_overdue_warning": "Time since last purchase is above historical rhythm.",
        "purchase_frequency_fluctuation_warning": "Recent purchase frequency is below baseline.",
        "purchase_quantity_fluctuation_warning": "Recent quantity is below baseline and needs review.",
        "terminal_loss_warning": "Object is in the monthly review list.",
        "new_terminal_detection": "Object is a new terminal attention item.",
    }.get(detector_name, "Structured business evidence.")


def _evidence_text(detector_name: str) -> str:
    return _detector_summary(detector_name)
