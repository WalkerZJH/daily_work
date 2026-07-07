"""Scope configuration for bounded frontend risk packages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FrontendScopeConfig:
    frontend_default_topn_per_manufacturer: int = 20
    frontend_max_topn_per_manufacturer: int = 50
    index_topn: int = 8
    detail_sample_topn: int = 20
    one_shot_topn_per_manufacturer: int = 20
    observation_topn_per_manufacturer: int = 20
    max_cards_per_entity: int = 5
    max_business_visible_evidence_per_card: int = 3
