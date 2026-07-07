"""Stable enums for the MVC-facing risk model package."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class RiskLevel(StrEnum):
    RED = "red"
    ORANGE = "orange"
    YELLOW = "yellow"
    OBSERVATION = "observation"
    INSUFFICIENT = "insufficient"
    ATTENTION = "attention"


class RiskColor(StrEnum):
    RED = "red"
    ORANGE = "orange"
    YELLOW = "yellow"
    GRAY = "gray"


class CandidateType(StrEnum):
    RECURRING = "recurring"
    ONE_SHOT = "one_shot"
    DEMAND_SHAPE_OBSERVATION = "demand_shape_observation"


class FinalCandidateStatus(StrEnum):
    PRIORITY_REVIEW = "priority_review"
    MANUAL_REVIEW = "manual_review"
    OBSERVATION_ONLY = "observation_only"
    LOW_CONFIDENCE_WATCH = "low_confidence_watch"
    ONE_SHOT_ATTENTION = "one_shot_attention"
    NOT_ACTIONABLE = "not_actionable"


class ReviewPriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class EvidenceStrength(StrEnum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"


class DisplayMode(StrEnum):
    SHOW_PROBABILITY = "show_probability"
    SHOW_RISK_BAND = "show_risk_band"
    SHOW_OBSERVATION_NOTE = "show_observation_note"
    HIDE_PROBABILITY = "hide_probability"


class ProbabilityDisplayLevel(StrEnum):
    PROBABILITY_ALLOWED = "probability_allowed"
    RISK_BAND_ONLY = "risk_band_only"
    OBSERVATION_ONLY = "observation_only"
    HIDDEN_DATA_INSUFFICIENT = "hidden_data_insufficient"


class VisibilityLevel(StrEnum):
    BUSINESS_VISIBLE = "business_visible"
    MANAGER_VISIBLE = "manager_visible"
    INTERNAL_ONLY = "internal_only"


class ReportType(StrEnum):
    MONTHLY = "monthly"
    DAILY = "daily"


class ExportFormat(StrEnum):
    HTML = "html"
    MARKDOWN = "markdown"
    CSV_BUNDLE = "csv_bundle"
    FUTURE_PDF = "future_pdf"
    FUTURE_XLSX = "future_xlsx"
