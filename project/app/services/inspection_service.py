from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import date
from hashlib import md5
from typing import Any

from app.adapters.base import DatasetBundle
from app.adapters.quality import DataQualityChecker
from app.detectors.fusion import fuse_detector_results as fuse_feature_detector_results
from app.detectors.order_level import run_order_level_detectors
from app.detectors.orchestrator import DetectorOrchestrator
from app.detectors.registry import build_default_detector_registry
from app.core.logging import log_inspection_summary
from app.features.snapshot import FeatureSnapshot
from app.schemas.algorithm import RiskClue
from app.schemas.api import DataSourceRequest, DryRunResponse
from app.schemas.config import AppConfig
from app.services.clue_management_service import ClueManagementService
from app.services.backbone_service import BackboneService
from app.services.feature_service import FeatureService
from app.services.user_config_service import UserConfigService

logger = logging.getLogger(__name__)


class InspectionService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def inspect_unit(
        self,
        source: DataSourceRequest,
        org_code: str,
        product_line_code: str,
        as_of_date: date,
    ) -> dict[str, Any]:
        return self.inspect_feature_unit(
            source,
            org_code,
            "product_line",
            product_line_code,
            as_of_date,
        )

    def dry_run(
        self,
        source: DataSourceRequest,
        as_of_date: date,
        user_id: str | None = None,
    ) -> DryRunResponse:
        user_config = UserConfigService().effective_detector_config(user_id or "admin")
        scoped_source = self._apply_user_scope(source, user_config)
        enabled_detectors = user_config["enabled_detectors"]
        registry = build_default_detector_registry()
        terminal_enabled = [name for name in enabled_detectors if name in registry.names()]
        feature_run = FeatureService(self.config).run_preprocess(scoped_source, as_of_date)
        detector_run = DetectorOrchestrator(registry).run(
            feature_run.snapshots,
            self.config,
            enabled_detectors=terminal_enabled,
        )
        results_by_unit = defaultdict(list)
        detector_hits: Counter[str] = Counter()
        for detector_result in detector_run.results:
            results_by_unit[detector_result.unit_id].append(detector_result)
            if detector_result.hit:
                detector_hits[detector_result.detector_name] += 1

        order_evidence_by_unit = run_order_level_detectors(
            feature_run.prepared_orders,
            as_of_date=as_of_date,
            enabled_detectors=enabled_detectors,
            recent_days=self.config.preprocessors.temporal_window.recent_days,
        )
        for evidence_list in order_evidence_by_unit.values():
            for evidence in evidence_list:
                if evidence.hit:
                    detector_hits[evidence.detector_id] += 1

        snapshots_by_unit = {snapshot.unit_id: snapshot for snapshot in feature_run.snapshots}
        backbone_predictions = BackboneService(self.config).predict_on_orders(
            feature_run.prepared_orders,
            as_of_date,
        )
        backbone_by_unit = {
            prediction.analysis_unit_id: prediction
            for prediction in backbone_predictions
        }
        risk_cards = ClueManagementService().build_candidates(
            snapshots_by_unit=snapshots_by_unit,
            terminal_results_by_unit=results_by_unit,
            order_evidence_by_unit=order_evidence_by_unit,
            prepared_orders=feature_run.prepared_orders,
            as_of_date=as_of_date,
            config_version=self.config.config_version,
            backbone_by_unit=backbone_by_unit,
        )
        clue_candidates = risk_cards
        level_counter = Counter({"red": 0, "orange": 0, "yellow": 0, "none": 0})
        level_counter.update(clue.risk_level for clue in clue_candidates)
        warning_summary = Counter(feature_run.warning_summary)
        for evidence_list in order_evidence_by_unit.values():
            for evidence in evidence_list:
                warning_summary.update(evidence.warnings)
        quality_report = DataQualityChecker().check_orders(
            feature_run.prepared_orders,
            feature_run.dataset_name,
        )
        for issue in quality_report.issues:
            warning_summary[issue.check_name] += issue.row_count
        data_quality_summary = {
            "dataset_name": quality_report.dataset_name,
            "total_rows": quality_report.total_rows,
            "error_count": quality_report.error_count,
            "warning_count": quality_report.warning_count,
            "issues": [issue.model_dump(mode="json") for issue in quality_report.issues],
        }

        response = DryRunResponse(
            dataset_name=feature_run.dataset_name,
            as_of_date=as_of_date,
            config_version=self.config.config_version,
            unit_count=len(feature_run.snapshots),
            clue_count=len(clue_candidates),
            risk_level_distribution=dict(level_counter),
            detector_hit_distribution=dict(detector_hits),
            top_risk_clues=clue_candidates[:20],
            risk_card_candidates=risk_cards[:20],
            enabled_preprocessors=feature_run.enabled_preprocessors,
            feature_count=feature_run.feature_count,
            detector_skipped_due_to_missing_features=detector_run.skipped_due_to_missing_features,
            warning_summary=dict(warning_summary),
            data_quality_summary=data_quality_summary,
            backbone={
                "active_prediction_count": len(backbone_predictions),
                "warnings": sorted(
                    {
                        warning
                        for prediction in backbone_predictions
                        for warning in prediction.warnings
                    }
                ),
            },
        )
        log_inspection_summary(
            logger,
            {
                "as_of_date": as_of_date.isoformat(),
                "config_version": self.config.config_version,
                "dataset_name": feature_run.dataset_name,
                "unit_count": response.unit_count,
                "clue_count": response.clue_count,
                "detector_hit_distribution": response.detector_hit_distribution,
            },
        )
        return response

    @staticmethod
    def _apply_user_scope(source: DataSourceRequest, user_config: dict[str, Any]) -> DataSourceRequest:
        region_scope = user_config.get("region_scope") or []
        if source.source_type == "database" and region_scope and not source.province:
            return source.model_copy(update={"province": region_scope[0]})
        return source

    def inspect_feature_unit(
        self,
        source: DataSourceRequest,
        org_code: str,
        analysis_grain: str,
        target_code: str,
        as_of_date: date,
    ) -> dict[str, Any]:
        feature_run, snapshot = FeatureService(self.config).get_snapshot(
            source, org_code, analysis_grain, target_code, as_of_date
        )
        if snapshot is None:
            return {
                "canonical_profile": {
                    "org_code": org_code,
                    "analysis_grain": analysis_grain,
                    "target_code": target_code,
                },
                "feature_snapshot": None,
                "detector_results": [],
                "fusion": {},
                "evidence": {"warnings": ["FEATURE_SNAPSHOT_NOT_FOUND"]},
            }
        detector_run = DetectorOrchestrator(build_default_detector_registry()).run(
            [snapshot],
            self.config,
        )
        fusion = fuse_feature_detector_results(detector_run.results, self.config)
        return {
            "canonical_profile": self._build_feature_profile(feature_run.bundle, snapshot),
            "feature_snapshot": snapshot.model_dump(mode="json"),
            "detector_results": [result.model_dump(mode="json") for result in detector_run.results],
            "fusion": fusion,
            "evidence": {
                "unit_id": snapshot.unit_id,
                "feature_versions": snapshot.feature_versions,
                "produced_by": snapshot.produced_by,
                "warnings": snapshot.warnings,
                "detector_warnings": {
                    result.detector_name: result.warnings
                    for result in detector_run.results
                    if result.warnings
                },
            },
        }

    def _build_feature_risk_clue(
        self,
        snapshot: FeatureSnapshot,
        detector_results: list[Any],
        fusion: dict[str, Any],
    ) -> RiskClue:
        trace_base = f"{snapshot.unit_id}|{snapshot.as_of_date}|{self.config.config_version}"
        debug_trace_id = md5(trace_base.encode("utf-8")).hexdigest()[:12]
        return RiskClue(
            clue_id=f"CLUE-{debug_trace_id}",
            org_code=snapshot.org_code,
            product_line_code=snapshot.target_code,
            risk_score=fusion["risk_score"],
            risk_level=fusion["risk_level"],
            triggered_detectors=fusion["triggered_detectors"],
            confidence=fusion["confidence"],
            evidence_summary_structured={
                "analysis_grain": snapshot.analysis_grain,
                "target_code": snapshot.target_code,
                "feature_snapshot": {
                    "unit_id": snapshot.unit_id,
                    "as_of_date": snapshot.as_of_date.isoformat(),
                    "features": snapshot.features,
                    "warnings": snapshot.warnings,
                },
                "detectors": [
                    result.model_dump(mode="json")
                    for result in detector_results
                    if result.hit or result.required_features_missing
                ],
                "triggered_families": fusion["triggered_families"],
            },
            debug_trace_id=debug_trace_id,
        )

    @staticmethod
    def _build_feature_profile(bundle: DatasetBundle, snapshot: FeatureSnapshot) -> dict[str, Any]:
        profile: dict[str, Any] = {
            "org_code": snapshot.org_code,
            "analysis_grain": snapshot.analysis_grain,
            "target_code": snapshot.target_code,
        }
        orgs = bundle.orgs
        if not orgs.empty and "org_code" in orgs.columns:
            match = orgs[orgs["org_code"].astype(str) == snapshot.org_code]
            if not match.empty:
                profile.update(match.iloc[0].dropna().to_dict())
        return profile
