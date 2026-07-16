"""Schema constants for detector result-batch sidecar tables."""

from __future__ import annotations


DETECTOR_CATALOG_COLUMNS = [
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

DAILY_DETECTOR_RUN_COLUMNS = [
    "detector_run_id",
    "detector_id",
    "detector_version",
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

DAILY_DETECTOR_CLUE_COLUMNS = [
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

HIGH_RISK_DETECTOR_EVIDENCE_COLUMNS = [
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


DETECTOR_TABLES = {
    "detector_catalog": DETECTOR_CATALOG_COLUMNS,
    "daily_detector_runs": DAILY_DETECTOR_RUN_COLUMNS,
    "daily_detector_clues": DAILY_DETECTOR_CLUE_COLUMNS,
    "high_risk_detector_evidence": HIGH_RISK_DETECTOR_EVIDENCE_COLUMNS,
}
