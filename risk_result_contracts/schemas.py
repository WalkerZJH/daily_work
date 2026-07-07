"""Standard table names and required columns for monthly risk result batches."""

from __future__ import annotations


STANDARD_TABLES = [
    "risk_entities",
    "risk_cards",
    "risk_card_evidence",
    "risk_entity_timeline",
    "hospital_aggregates",
    "drug_aggregates",
    "monthly_reports",
    "proof_cases",
    "work_order_reserved",
]

RISK_ENTITY_REQUIRED_COLUMNS = [
    "risk_entity_id",
    "candidate_id",
    "tenant_id",
    "manufacturer_code",
    "hospital_code",
    "drug_group",
    "report_month",
    "risk_level",
    "review_status",
    "final_candidate_status",
    "auto_dispatch_allowed",
]

RISK_CARD_REQUIRED_COLUMNS = [
    "risk_card_id",
    "risk_entity_id",
    "candidate_id",
    "card_type",
    "card_title",
    "card_level",
    "source_module",
    "is_primary",
]

RISK_EVIDENCE_REQUIRED_COLUMNS = [
    "evidence_id",
    "risk_card_id",
    "risk_entity_id",
    "candidate_id",
    "evidence_type",
    "evidence_text",
    "visibility_level",
]

MONTHLY_REPORT_REQUIRED_COLUMNS = [
    "monthly_report_id",
    "report_type",
    "report_month",
    "title",
    "summary_text",
]
