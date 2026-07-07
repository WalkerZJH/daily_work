"""Shared enums for risk result batch producers and consumers."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class ReportType(StrEnum):
    MONTHLY = "monthly"


class DataBackend(StrEnum):
    PARQUET = "parquet"
    CSV = "csv"


class CandidateType(StrEnum):
    RECURRING = "recurring"
    ONE_SHOT = "one_shot"
    OBSERVATION = "observation"


class VisibilityLevel(StrEnum):
    BUSINESS_VISIBLE = "business_visible"
    MANAGER_VISIBLE = "manager_visible"
    INTERNAL_ONLY = "internal_only"
