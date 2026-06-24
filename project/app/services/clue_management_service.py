from __future__ import annotations

from collections import defaultdict
from datetime import date
from hashlib import md5
from typing import Any

import pandas as pd

from app.detectors.base import DetectorResult
from app.detectors.registry import DETECTOR_META
from app.features.snapshot import FeatureSnapshot
from app.schemas.backbone import BackbonePrediction
from app.schemas.algorithm import (
    BackboneSignal,
    DetectorEvidence,
    EvidenceFamily,
    RiskCardCandidate,
)


class ClueManagementService:
    def build_candidates(
        self,
        *,
        snapshots_by_unit: dict[str, FeatureSnapshot],
        terminal_results_by_unit: dict[str, list[DetectorResult]],
        order_evidence_by_unit: dict[str, list[DetectorEvidence]],
        prepared_orders: pd.DataFrame,
        as_of_date: date,
        config_version: str,
        backbone_by_unit: dict[str, BackbonePrediction] | None = None,
    ) -> list[RiskCardCandidate]:
        candidates: list[RiskCardCandidate] = []
        all_units = set(terminal_results_by_unit) | set(order_evidence_by_unit)
        for unit_id in all_units:
            snapshot = snapshots_by_unit.get(unit_id)
            if snapshot is None:
                continue
            if snapshot.analysis_grain != "product_line":
                continue
            evidence = [
                *self._terminal_evidence(terminal_results_by_unit.get(unit_id, [])),
                *order_evidence_by_unit.get(unit_id, []),
            ]
            hit_evidence = [item for item in evidence if item.hit]
            if not hit_evidence:
                continue
            profile = self._profile(prepared_orders, snapshot)
            candidates.append(
                self._build_candidate(
                    snapshot=snapshot,
                    profile=profile,
                    evidence=hit_evidence,
                    as_of_date=as_of_date,
                    config_version=config_version,
                    backbone_prediction=(backbone_by_unit or {}).get(unit_id),
                )
            )
        candidates.sort(
            key=lambda card: (card.risk_level == "red", card.rule_score or 0, card.confidence),
            reverse=True,
        )
        return candidates

    def _build_candidate(
        self,
        *,
        snapshot: FeatureSnapshot,
        profile: dict[str, Any],
        evidence: list[DetectorEvidence],
        as_of_date: date,
        config_version: str,
        backbone_prediction: BackbonePrediction | None = None,
    ) -> RiskCardCandidate:
        families = self._families(evidence)
        categories = {item.category for item in evidence}
        category = "price_warning" if "price_warning" in categories else sorted(categories)[0]
        backbone = self._backbone_signal(backbone_prediction)
        risk_level = self._risk_level(category, families, evidence, backbone)
        rule_score = max(item.severity for item in evidence)
        confidence = max(item.confidence for item in evidence)
        warnings = list(
            dict.fromkeys(
                [
                    *backbone.warnings,
                    *snapshot.warnings,
                    *[warning for item in evidence for warning in item.warnings],
                ]
            )
        )
        trace_base = f"{snapshot.unit_id}|{as_of_date}|{config_version}|{category}"
        debug_trace_id = md5(trace_base.encode("utf-8")).hexdigest()[:12]
        title = self._title(category, risk_level, profile, snapshot)
        related_entities = self._related_entities(profile, evidence)
        return RiskCardCandidate(
            card_id=f"RISK-{debug_trace_id}",
            as_of_date=as_of_date,
            category=category,
            risk_level=risk_level,
            title=title,
            org_code=snapshot.org_code,
            org_name=profile.get("org_name"),
            product_line_code=snapshot.target_code,
            product_line_name=profile.get("product_line_name") or snapshot.target_code,
            province=profile.get("province"),
            city=profile.get("city"),
            county=profile.get("county"),
            backbone=backbone,
            evidence_families=families,
            detector_evidence=evidence,
            related_entities=related_entities,
            suggested_action=self._suggested_action(category),
            warnings=warnings,
            data_quality_summary={},
            debug_trace_id=debug_trace_id,
            rule_score=round(rule_score, 2),
            risk_score_deprecated=round(rule_score, 2),
            triggered_detectors=[item.detector_id for item in evidence],
            confidence=round(confidence, 4),
            evidence_summary_structured={
                "rule_score_note": "rule_score is an uncalibrated sorting signal, not probability.",
                "feature_snapshot": {
                    "unit_id": snapshot.unit_id,
                    "features": snapshot.features,
                    "warnings": snapshot.warnings,
                },
            },
            llm_context={
                "do_not_call_llm": True,
                "category": category,
                "evidence_family_count": len(families),
                "detector_ids": [item.detector_id for item in evidence],
            },
        )

    @staticmethod
    def _backbone_signal(prediction: BackbonePrediction | None) -> BackboneSignal:
        if prediction is None:
            return BackboneSignal()
        return BackboneSignal(
            backbone_model=prediction.model_name,  # type: ignore[arg-type]
            model_name=prediction.model_name,
            model_version=prediction.model_version,
            selected_model_name=prediction.selected_model_name,
            p_alive=prediction.p_alive,
            backbone_risk_score=prediction.backbone_risk_score,
            backbone_confidence=prediction.confidence,
            confidence=prediction.confidence,
            warnings=prediction.warnings,
            debug_features=prediction.debug_features,
            data_sufficiency=prediction.data_sufficiency,
        )

    @staticmethod
    def _terminal_evidence(results: list[DetectorResult]) -> list[DetectorEvidence]:
        output: list[DetectorEvidence] = []
        for result in results:
            meta = DETECTOR_META[result.detector_name]
            output.append(
                DetectorEvidence(
                    detector_id=result.detector_name,
                    category=meta.category,
                    family=meta.family,
                    hit=result.hit,
                    severity=result.severity,
                    confidence=result.confidence,
                    reason_code=result.reason_code,
                    evidence_items=result.evidence_refs,
                    related_entities={
                        "org_code": result.org_code,
                        "analysis_grain": result.analysis_grain,
                        "product_line_code": result.target_code,
                    },
                    warnings=result.warnings,
                    sample_order_ids=[
                        str(ref.get("order_id"))
                        for ref in result.evidence_refs
                        if ref.get("order_id") is not None
                    ],
                    statistics=result.metrics,
                )
            )
        return output

    @staticmethod
    def _families(evidence: list[DetectorEvidence]) -> list[EvidenceFamily]:
        grouped: dict[tuple[str, str], list[DetectorEvidence]] = defaultdict(list)
        for item in evidence:
            grouped[(item.category, item.family)].append(item)
        families: list[EvidenceFamily] = []
        for (category, family), items in grouped.items():
            families.append(
                EvidenceFamily(
                    category=category,
                    family=family,
                    detector_ids=[item.detector_id for item in items],
                    max_severity=max(item.severity for item in items),
                    hit_count=len(items),
                    reason_codes=sorted({item.reason_code for item in items}),
                )
            )
        return sorted(families, key=lambda item: (item.category, item.family))

    @staticmethod
    def _risk_level(
        category: str,
        families: list[EvidenceFamily],
        evidence: list[DetectorEvidence],
        backbone: BackboneSignal,
    ) -> str:
        max_severity = max(item.severity for item in evidence)
        hard_rule = category in {"price_warning", "delivery_response"}
        if hard_rule and max_severity >= 85:
            return "red"
        if hard_rule and max_severity >= 55:
            return "orange"
        if backbone.p_alive is not None and backbone.p_alive < 0.3 and len(families) >= 2:
            return "red"
        if len(families) >= 2 or max_severity >= 55:
            return "orange"
        return "yellow"

    @staticmethod
    def _profile(orders: pd.DataFrame, snapshot: FeatureSnapshot) -> dict[str, Any]:
        if orders.empty:
            return {}
        scoped = orders[
            (orders["org_code"].astype(str) == snapshot.org_code)
            & (orders["product_line_code"].astype(str) == snapshot.target_code)
        ]
        if scoped.empty:
            return {}
        row = scoped.sort_values("order_time").iloc[-1]
        keys = ["org_name", "product_line_name", "province", "city", "county"]
        return {key: row.get(key) for key in keys if key in row and pd.notna(row.get(key))}

    @staticmethod
    def _related_entities(
        profile: dict[str, Any],
        evidence: list[DetectorEvidence],
    ) -> dict[str, Any]:
        related: dict[str, Any] = {"profile": profile, "evidence_entities": []}
        for item in evidence:
            if item.related_entities:
                related["evidence_entities"].append(item.related_entities)
        return related

    @staticmethod
    def _title(category: str, risk_level: str, profile: dict[str, Any], snapshot: FeatureSnapshot) -> str:
        name = profile.get("product_line_name") or snapshot.target_code
        if category == "price_warning":
            return f"{name} price warning ({risk_level})"
        if category == "delivery_response":
            return f"{name} delivery response warning ({risk_level})"
        return f"{name} terminal change warning ({risk_level})"

    @staticmethod
    def _suggested_action(category: str) -> str:
        if category == "price_warning":
            return "Review comparable unit price, configured warning price, and recent order samples."
        if category == "delivery_response":
            return "Check distributor response status and recent fulfillment records."
        return "Review terminal activity evidence; do not interpret rule_score as churn probability."
