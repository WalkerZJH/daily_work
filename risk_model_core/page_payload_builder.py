"""Page payload builder for backend MVC integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .repositories import RiskResultRepository


class PagePayloadBuilder:
    def __init__(self, repository: RiskResultRepository):
        self.repository = repository

    def build_index_payload(self) -> dict[str, Any]:
        return self._payload_or_build("index_payload", self._build_index_payload)

    def build_clues_payload(self) -> dict[str, Any]:
        return self._payload_or_build("clues_payload", self._build_clues_payload)

    def build_clue_detail_payload(self, risk_entity_id: str) -> dict[str, Any]:
        entity = self.repository.get_risk_entity(risk_entity_id)
        if entity is None:
            raise KeyError(risk_entity_id)
        cards = self.repository.list_risk_cards(risk_entity_id).to_dict("records")
        for card in cards:
            card["evidence"] = self.repository.list_evidence(str(card["risk_card_id"])).to_dict("records")
        return {"risk_entity": entity, "risk_cards": cards, "auto_dispatch_allowed": False}

    def build_watchlist_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "watchlist_payload",
            lambda: {"items": self.repository.list_risk_entities(is_observation=True).to_dict("records")},
        )

    def build_dashboard_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "dashboard_payload",
            lambda: {"kpi_cards": {"feedback": "pending feedback integration"}},
        )

    def build_backtest_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "backtest_payload",
            lambda: {"proof_case_report_allowed": False, "placeholder_cases": []},
        )

    def build_verify_payload(self) -> dict[str, Any]:
        return self._payload_or_build("verify_payload", lambda: {"verification_enabled": False})

    def build_distributor_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "distributor_payload",
            lambda: {"delivery_detector_enabled": False, "alerts": []},
        )

    def _payload_or_build(self, page_name: str, builder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            return self.repository.get_page_payload(page_name)
        except FileNotFoundError:
            return builder()

    def _build_index_payload(self) -> dict[str, Any]:
        entities = self.repository.list_risk_entities()
        high_risk_count = int(entities["is_high_risk"].sum()) if "is_high_risk" in entities else 0
        return {
            "page_title": "workbench",
            "top_clues": entities.head(8).to_dict("records"),
            "hero": {
                "high_risk_entity_count": high_risk_count,
                "auto_dispatch_allowed": False,
            },
        }

    def _build_clues_payload(self) -> dict[str, Any]:
        entities = self.repository.list_risk_entities()
        return {"items": entities.to_dict("records"), "pagination": {"total_items": len(entities)}}
