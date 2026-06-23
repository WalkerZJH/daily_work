from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import date
from hashlib import md5
from typing import Any

import pandas as pd

from app.adapters.base import DatasetBundle
from app.adapters.csv_adapter import CSVSourceAdapter
from app.detectors.fusion import fuse_detector_results as fuse_feature_detector_results
from app.detectors.orchestrator import DetectorOrchestrator
from app.detectors.registry import build_default_detector_registry
from app.algorithms.baseline import calculate_unit_baseline_metrics, filter_unit_orders
from app.algorithms.demand_shape import calculate_demand_shape
from app.algorithms.detectors.frequency_drop import detect_frequency_drop
from app.algorithms.detectors.inactive_terminal import detect_inactive_terminal
from app.algorithms.detectors.ip_interval import detect_ip_interval
from app.algorithms.detectors.new_terminal import detect_new_terminal
from app.algorithms.detectors.sku_shrink import detect_sku_shrink
from app.algorithms.evidence import build_structured_evidence
from app.algorithms.fusion import build_risk_clue, fuse_detector_results
from app.core.logging import log_inspection_summary
from app.features.snapshot import FeatureSnapshot
from app.schemas.algorithm import DetectorResult, RiskClue, UnitInspectionResult
from app.schemas.api import DataSourceRequest, DryRunResponse
from app.schemas.config import AppConfig
from app.services.feature_service import FeatureService

logger = logging.getLogger(__name__)


class InspectionService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def load_dataset(self, source: DataSourceRequest) -> DatasetBundle:
        adapter = CSVSourceAdapter(dataset_name=source.dataset_name, csv_path=source.csv_path)
        return adapter.load_dataset()

    def prepare_orders(self, bundle: DatasetBundle) -> pd.DataFrame:
        orders = bundle.orders.copy()
        if orders.empty:
            return orders

        orders["order_time"] = pd.to_datetime(orders["order_time"], errors="coerce")
        for numeric_field in [
            "purchase_qty",
            "purchase_amount",
            "purchase_price",
            "delivery_qty",
            "receipt_qty",
        ]:
            if numeric_field in orders.columns:
                orders[numeric_field] = pd.to_numeric(orders[numeric_field], errors="coerce")

        mapping = bundle.product_line_mapping.copy()
        if not mapping.empty and "drug_code" in mapping.columns:
            mapping_cols = [
                column
                for column in ["drug_code", "product_line_code", "product_line_name"]
                if column in mapping.columns
            ]
            orders = orders.merge(
                mapping[mapping_cols].drop_duplicates("drug_code"), on="drug_code", how="left"
            )

        drugs = bundle.drugs.copy()
        if not drugs.empty and "drug_code" in drugs.columns:
            metadata_cols = [
                column
                for column in ["drug_code", "drug_name", "spec", "dosage_form", "approval_no"]
                if column in drugs.columns
                and (column == "drug_code" or column not in orders.columns)
            ]
            if len(metadata_cols) > 1:
                orders = orders.merge(
                    drugs[metadata_cols].drop_duplicates("drug_code"),
                    on="drug_code",
                    how="left",
                )

        if "product_line_code" not in orders.columns:
            orders["product_line_code"] = orders["drug_code"].astype(str)
        orders["product_line_code"] = orders["product_line_code"].fillna("UNKNOWN").astype(str)
        if "product_line_name" not in orders.columns:
            orders["product_line_name"] = orders["product_line_code"]
        orders["product_line_name"] = (
            orders["product_line_name"].fillna(orders["product_line_code"]).astype(str)
        )
        return orders

    def inspect_unit(
        self,
        source: DataSourceRequest,
        org_code: str,
        product_line_code: str,
        as_of_date: date,
    ) -> UnitInspectionResult:
        bundle = self.load_dataset(source)
        prepared_orders = self.prepare_orders(bundle)
        return self._inspect_unit_prepared(
            bundle, prepared_orders, org_code, product_line_code, as_of_date
        )

    def dry_run(self, source: DataSourceRequest, as_of_date: date) -> DryRunResponse:
        feature_run = FeatureService(self.config).run_preprocess(source, as_of_date)
        detector_run = DetectorOrchestrator(build_default_detector_registry()).run(
            feature_run.snapshots,
            self.config,
        )
        results_by_unit = defaultdict(list)
        detector_hits: Counter[str] = Counter()
        for detector_result in detector_run.results:
            results_by_unit[detector_result.unit_id].append(detector_result)
            if detector_result.hit:
                detector_hits[detector_result.detector_name] += 1

        snapshots_by_unit = {snapshot.unit_id: snapshot for snapshot in feature_run.snapshots}
        clue_candidates: list[RiskClue] = []
        for unit_key, detector_results in results_by_unit.items():
            snapshot = snapshots_by_unit.get(unit_key)
            if snapshot is None or snapshot.analysis_grain != "product_line":
                continue
            fusion = fuse_feature_detector_results(detector_results, self.config)
            if not fusion["triggered_detectors"] or fusion["risk_level"] == "none":
                continue
            clue_candidates.append(self._build_feature_risk_clue(snapshot, detector_results, fusion))

        clue_candidates.sort(key=lambda clue: (clue.risk_score, clue.confidence), reverse=True)
        level_counter = Counter({"red": 0, "orange": 0, "yellow": 0, "none": 0})
        level_counter.update(clue.risk_level for clue in clue_candidates)

        response = DryRunResponse(
            dataset_name=feature_run.dataset_name,
            as_of_date=as_of_date,
            config_version=self.config.config_version,
            unit_count=len(feature_run.snapshots),
            clue_count=len(clue_candidates),
            risk_level_distribution=dict(level_counter),
            detector_hit_distribution=dict(detector_hits),
            top_risk_clues=clue_candidates[:20],
            enabled_preprocessors=feature_run.enabled_preprocessors,
            feature_count=feature_run.feature_count,
            detector_skipped_due_to_missing_features=detector_run.skipped_due_to_missing_features,
            warning_summary=feature_run.warning_summary,
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

    def _inspect_unit_prepared(
        self,
        bundle: DatasetBundle,
        prepared_orders: pd.DataFrame,
        org_code: str,
        product_line_code: str,
        as_of_date: date,
    ) -> UnitInspectionResult:
        unit_orders = filter_unit_orders(prepared_orders, org_code, product_line_code, as_of_date)
        metrics = calculate_unit_baseline_metrics(
            unit_orders=unit_orders,
            org_code=org_code,
            product_line_code=product_line_code,
            as_of_date=as_of_date,
            recent_days=self.config.windows.recent_days,
            baseline_days=self.config.windows.baseline_days,
        )
        demand_shape = calculate_demand_shape(
            unit_orders=unit_orders,
            as_of_date=as_of_date,
            config=self.config.demand_shape,
            lookback_days=self.config.windows.baseline_days,
        )
        detector_results = self._run_detectors(unit_orders, metrics, as_of_date)
        fusion = fuse_detector_results(detector_results, self.config.fusion)
        evidence = build_structured_evidence(metrics, demand_shape, detector_results)
        clue = build_risk_clue(
            org_code=org_code,
            product_line_code=product_line_code,
            as_of_date=as_of_date,
            config_version=self.config.config_version,
            fusion=fusion,
            evidence_summary=evidence,
        )

        return UnitInspectionResult(
            profile=self._build_profile(bundle, prepared_orders, org_code, product_line_code),
            demand_shape=demand_shape,
            baseline_metrics=metrics,
            detector_results=detector_results,
            fusion=fusion,
            evidence_json=evidence,
            clue=clue,
        )

    def _run_detectors(
        self,
        unit_orders: pd.DataFrame,
        metrics: Any,
        as_of_date: date,
    ) -> list[DetectorResult]:
        results: list[DetectorResult] = []
        detector_config = self.config.detectors
        if detector_config.ip_interval.enabled:
            results.append(detect_ip_interval(unit_orders, as_of_date, detector_config.ip_interval))
        if detector_config.frequency_drop.enabled:
            results.append(detect_frequency_drop(metrics, detector_config.frequency_drop))
        if detector_config.sku_shrink.enabled:
            results.append(detect_sku_shrink(metrics, detector_config.sku_shrink))
        if detector_config.inactive_terminal.enabled:
            results.append(
                detect_inactive_terminal(unit_orders, as_of_date, detector_config.inactive_terminal)
            )
        if detector_config.new_terminal.enabled:
            results.append(
                detect_new_terminal(unit_orders, metrics, as_of_date, detector_config.new_terminal)
            )
        return results

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

    @staticmethod
    def _build_profile(
        bundle: DatasetBundle,
        prepared_orders: pd.DataFrame,
        org_code: str,
        product_line_code: str,
    ) -> dict[str, Any]:
        profile: dict[str, Any] = {"org_code": org_code, "product_line_code": product_line_code}
        orgs = bundle.orgs
        if not orgs.empty and "org_code" in orgs.columns:
            match = orgs[orgs["org_code"].astype(str) == str(org_code)]
            if not match.empty:
                profile.update(match.iloc[0].dropna().to_dict())
        unit_orders = prepared_orders[
            (prepared_orders["org_code"].astype(str) == str(org_code))
            & (prepared_orders["product_line_code"].astype(str) == str(product_line_code))
        ]
        if not unit_orders.empty and "product_line_name" in unit_orders.columns:
            profile["product_line_name"] = str(unit_orders["product_line_name"].dropna().iloc[0])
        return profile
