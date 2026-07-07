"""Safe deterministic business copy for risk result objects."""

from __future__ import annotations

from typing import Any


FORBIDDEN_CLAIMS = [
    "\u533b\u9662\u5df2\u7ecf\u786e\u5b9a\u6d41\u5931",
    "\u533b\u9662\u4e00\u5b9a\u4e0d\u4f1a\u518d\u91c7\u8d2d",
    "\u533b\u9662\u4e3b\u52a8\u5f03\u7528",
    "\u7ade\u54c1\u66ff\u4ee3\u5df2\u53d1\u751f",
    "\u653f\u7b56\u843d\u6807\u5df2\u53d1\u751f",
    "\u914d\u9001\u5546\u8d23\u4efb\u5df2\u786e\u8ba4",
    "\u4ef7\u683c\u5f02\u5e38\u5bfc\u81f4\u6d41\u5931",
    "\u4f4e\u98ce\u9669\u5bf9\u8c61\u4e00\u5b9a\u5b89\u5168",
    "\u9ad8\u98ce\u9669\u5bf9\u8c61\u4e00\u5b9a\u6d41\u5931",
]


class BusinessCopyRenderer:
    def render_entity_summary(self, entity: dict[str, Any]) -> str:
        if bool(entity.get("is_one_shot")):
            text = "New terminal attention item; do not interpret it as recurring churn."
        elif bool(entity.get("is_observation")):
            text = "Observation item; continue monitoring and do not treat it as high risk."
        else:
            text = "Monthly risk review item; business staff should verify recent purchasing context."
        validate_no_forbidden_claims(text)
        return text

    def render_card_summary(self, card: dict[str, Any], evidence: list[dict[str, Any]] | None = None) -> str:
        text = str(card.get("card_summary") or card.get("card_title") or "Business review evidence.")
        validate_no_forbidden_claims(text)
        return text

    def render_suggested_action(
        self,
        entity: dict[str, Any],
        card: dict[str, Any],
        evidence: list[dict[str, Any]] | None = None,
    ) -> str:
        if bool(entity.get("is_one_shot")):
            text = "Check whether a second purchase can be encouraged."
        elif bool(entity.get("is_observation")):
            text = "Keep observing; do not treat this as a strong warning."
        else:
            text = str(card.get("suggested_action") or "Review recent purchasing plans and demand context manually.")
        validate_no_forbidden_claims(text)
        return text


def validate_no_forbidden_claims(text: str) -> None:
    bad = [term for term in FORBIDDEN_CLAIMS if term in text]
    if bad:
        raise ValueError(f"Forbidden claims found: {bad}")
