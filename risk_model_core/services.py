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

    def list_rankable_entities(
        self,
        *,
        manufacturer_codes: list[str] | None = None,
        report_month: str | None = None,
        horizon: str | None = None,
        candidate_type: str | list[str] | None = None,
        sort_by: str | list[str] | None = None,
        ascending: bool = False,
        limit: int | None = None,
        target_min: int | None = None,
    ) -> dict[str, Any]:
        """Return sortable rows for a backend-resolved user visibility scope.

        The backend owns org/user permission resolution and any 20-50 item fill
        policy. This service only applies the already resolved manufacturer
        filter, preserves rankable fields, and reports count metadata.
        """
        available = self.repository.list_rankable_entities(
            manufacturer_codes=manufacturer_codes,
            report_month=report_month,
            horizon=horizon,
            candidate_type=candidate_type,
            sort_by=sort_by,
            ascending=ascending,
            limit=None,
        )
        rows = available if limit is None else available.head(max(int(limit), 0))
        shortage_count = 0
        if target_min is not None:
            shortage_count = max(int(target_min) - len(rows), 0)
        return {
            "items": rows.to_dict("records"),
            "available_count": int(len(available)),
            "returned_count": int(len(rows)),
            "shortage_count": int(shortage_count),
            "scope": {
                "manufacturer_codes": [str(code) for code in manufacturer_codes] if manufacturer_codes is not None else None,
                "scope_resolved_by_backend": True,
                "manufacturer_code_is_user_scope": False,
            },
            "filters": {
                "report_month": report_month,
                "horizon": horizon,
                "candidate_type": candidate_type,
            },
            "sort_by": sort_by,
        }

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
