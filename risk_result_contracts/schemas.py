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
    "entity_display_lookup",
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

ENTITY_DISPLAY_LOOKUP_REQUIRED_COLUMNS = [
    "tenant_id",
    "report_month",
    "manufacturer_code",
    "manufacturer_display_name",
    "hospital_code",
    "hospital_display_name",
    "drug_code",
    "drug_group",
    "drug_display_name",
    "product_line_code",
    "product_line_name",
    "region_code",
    "region_display_name",
    "display_key",
    "display_name_source",
    "display_name_quality",
    "source_raw_batch_id",
    "updated_at",
]

ENTITY_DISPLAY_LOOKUP_UNIQUE_KEY = [
    "tenant_id",
    "report_month",
    "manufacturer_code",
    "hospital_code",
    "drug_group",
]
