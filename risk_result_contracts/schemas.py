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
    "detector_catalog",
    "daily_detector_runs",
    "daily_detector_clues",
    "high_risk_detector_evidence",
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

DETECTOR_CATALOG_REQUIRED_COLUMNS = [
    "detector_id",
    "detector_family",
    "detector_name",
    "status",
    "enabled_by_default",
    "method",
    "required_fields",
    "optional_fields",
    "output_schema_version",
    "caveat",
]

DAILY_DETECTOR_RUN_REQUIRED_COLUMNS = [
    "detector_run_id",
    "run_date",
    "report_month",
    "source_raw_batch_id",
    "source_result_batch_id",
    "detector_config_version",
    "enabled_detectors",
    "scanned_entity_count",
    "clue_count",
    "attached_high_risk_count",
    "created_at",
]

DAILY_DETECTOR_CLUE_REQUIRED_COLUMNS = [
    "detector_clue_id",
    "detector_run_id",
    "run_date",
    "tenant_id",
    "manufacturer_code",
    "hospital_code",
    "drug_group",
    "detector_id",
    "detector_family",
    "detector_score",
    "detector_level",
    "confidence",
    "hit_flag",
    "root_cause_label",
    "evidence_text",
    "evidence_payload",
    "is_monthly_high_risk_entity",
    "risk_entity_id",
    "monthly_risk_probability",
    "monthly_loss_value",
    "display_rank",
    "caveat",
    "created_at",
]

HIGH_RISK_DETECTOR_EVIDENCE_REQUIRED_COLUMNS = [
    "risk_entity_id",
    "detector_run_id",
    "run_date",
    "detector_id",
    "detector_family",
    "detector_score",
    "confidence",
    "root_cause_label",
    "evidence_text",
    "evidence_payload",
    "caveat",
    "created_at",
]
