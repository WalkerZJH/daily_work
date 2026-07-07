"""Service layer over risk result repositories."""

from __future__ import annotations

from typing import Any

from .business_copy_renderer import BusinessCopyRenderer
from .repositories import RiskResultRepository


class RiskQueryService:
    def __init__(self, repository: RiskResultRepository):
        self.repository = repository

    def list_entities(self, **filters: Any) -> list[dict[str, Any]]:
        return self.repository.list_risk_entities(**filters).to_dict("records")

    def get_detail(self, risk_entity_id: str) -> dict[str, Any]:
        entity = self.repository.get_risk_entity(risk_entity_id)
        if entity is None:
            raise KeyError(risk_entity_id)
        cards = self.repository.list_risk_cards(risk_entity_id).to_dict("records")
        for card in cards:
            card["evidence"] = self.repository.list_evidence(str(card["risk_card_id"])).to_dict("records")
        return {"entity": entity, "cards": cards, "timeline": self.repository.list_timeline(risk_entity_id).to_dict("records")}


class RiskCardService:
    def __init__(self, repository: RiskResultRepository, renderer: BusinessCopyRenderer | None = None):
        self.repository = repository
        self.renderer = renderer or BusinessCopyRenderer()

    def list_cards_with_copy(self, risk_entity_id: str) -> list[dict[str, Any]]:
        entity = self.repository.get_risk_entity(risk_entity_id) or {}
        cards = self.repository.list_risk_cards(risk_entity_id).to_dict("records")
        for card in cards:
            evidence = self.repository.list_evidence(str(card["risk_card_id"])).to_dict("records")
            card["safe_summary"] = self.renderer.render_card_summary(card, evidence)
            card["suggested_action"] = self.renderer.render_suggested_action(entity, card, evidence)
            card["evidence"] = evidence
        return cards


class ReportService:
    def __init__(self, repository: RiskResultRepository):
        self.repository = repository

    def list_reports(self, **filters: Any) -> list[dict[str, Any]]:
        return self.repository.list_monthly_reports(**filters).to_dict("records")

    def monthly_dashboard(self) -> dict[str, Any]:
        return self.repository.get_page_payload("dashboard_payload")


class ProofCaseService:
    def __init__(self, repository: RiskResultRepository):
        self.repository = repository

    def list_proof_cases(self, **filters: Any) -> list[dict[str, Any]]:
        return self.repository.list_proof_cases(**filters).to_dict("records")


class PermissionScopeService:
    """Reserved hook for tenant/org permissions in backend integration."""

    def can_view_entity(self, *_: Any, **__: Any) -> bool:
        return True
