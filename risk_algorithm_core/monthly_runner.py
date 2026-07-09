"""End-to-end monthly risk algorithm runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import pandas as pd

from risk_model_core.validation import validate_batch as validate_model_core_batch
from risk_result_contracts import validate_result_batch

from .artifact_loader import load_current_model_artifact
from .candidate_selector import BoundedCandidateSelector
from .config import MonthlyRiskRunConfig, load_run_config
from .detector_quality_gate import DetectorQualityGate
from .detectors import (
    DisabledDetectorNoteBuilder,
    FrequencyDropDetector,
    IntervalOverdueDetector,
    OneShotAttentionDetector,
    QuantityDropDetector,
    TerminalLossDetector,
)
from .entity_builder import build_monthly_entities
from .evidence_builder import build_risk_card_evidence, build_risk_cards
from .feature_engineering import engineer_features, engineer_features_from_facts
from .normalization import normalize_raw_tables
from .production_feature_builder import build_model_feature_frame
from .raw_input import read_raw_input_batch
from .result_assembler import assemble_result_batch
from .scorer import ArtifactRiskScorer, RuleBaselineScorer
from .status_decider import StatusDecider


class MonthlyRiskRunner:
    def __init__(self, config: MonthlyRiskRunConfig):
        self.config = config

    @classmethod
    def from_config_file(cls, config_path: str | Path) -> "MonthlyRiskRunner":
        return cls(load_run_config(config_path))

    def run(self, use_rule_baseline: bool = False) -> dict[str, Any]:
        cfg = self.config
        if cfg.report_type != "monthly":
            raise ValueError("risk_algorithm_core only supports monthly report_type.")
        report_month = cfg.resolved_report_month
        cutoff_date = cfg.resolved_cutoff_date
        raw_batch = read_raw_input_batch(cfg.raw_batch_dir, cfg.schema_mapping_path)
        normalized, normalize_report = normalize_raw_tables(raw_batch.tables, cutoff_date)
        entity_base = build_monthly_entities(
            normalized["orders"],
            normalized["drug_master"],
            normalized["hospital_master"],
            normalized["product_line_mapping"],
            report_month,
            cutoff_date,
            cfg.available_horizons,
        )
        if not normalized.get("fact_entity_month", pd.DataFrame()).empty:
            features, feature_report = engineer_features_from_facts(entity_base, normalized["fact_entity_month"], cutoff_date)
        else:
            features, feature_report = engineer_features(entity_base, normalized["orders"], cutoff_date)
        if use_rule_baseline:
            scorer = RuleBaselineScorer()
            model_artifact_id = "dry_run_rule_baseline"
            model_features = features
            feature_parity_report = pd.DataFrame()
            artifact_metadata = {
                "model_family": "rule_baseline",
                "feature_group": "dry_run",
                "calibration": "none",
                "excludes_choice_set": True,
                "feature_schema_version": "dry_run_rule_baseline",
            }
        else:
            artifact = load_current_model_artifact(cfg.artifact_dir, cfg.require_artifact)
            aligned = build_model_feature_frame(features, artifact)
            model_features = aligned.model_feature_frame
            feature_parity_report = aligned.parity_report
            scorer = ArtifactRiskScorer(artifact)
            model_artifact_id = artifact.manifest.artifact_id
            artifact_metadata = artifact.manifest.raw
        score_frame = scorer.score(model_features)
        selected, selection_report = BoundedCandidateSelector(cfg.worklist).select(score_frame, features)
        gate = DetectorQualityGate(cfg.detectors)
        gate_decisions = gate.evaluate(features, normalized)
        detector_outputs = self._run_detectors(selected, features, gate_decisions)
        disabled_notes = DisabledDetectorNoteBuilder().build(gate_decisions)
        status = StatusDecider().decide(selected, features, detector_outputs)
        risk_cards = build_risk_cards(status, detector_outputs)
        risk_evidence = build_risk_card_evidence(risk_cards, detector_outputs)
        write_parquet = bool(cfg.export.get("write_parquet", True))
        batch_dir = assemble_result_batch(
            cfg.output_root,
            cfg.run_id if cfg.run_id != "auto" else "auto",
            report_month,
            cutoff_date,
            raw_batch.manifest.raw_batch_id,
            model_artifact_id,
            cfg.primary_horizon,
            cfg.available_horizons,
            status,
            risk_cards,
            risk_evidence,
            features,
            cfg.worklist,
            score_frame=score_frame,
            normalized_tables=normalized,
            artifact_metadata=artifact_metadata,
            write_parquet=write_parquet,
        )
        validate_result_batch(batch_dir)
        validate_model_core_batch(batch_dir)
        summary = {
            "report_month": report_month,
            "cutoff_date": cutoff_date,
            "raw_batch_id": raw_batch.manifest.raw_batch_id,
            "entity_rows": int(len(entity_base)),
            "feature_rows": int(len(features)),
            "score_rows": int(len(score_frame)),
            "selected_candidate_rows": int(len(selected)),
            "detector_output_rows": int(len(detector_outputs)),
            "risk_card_rows": int(len(risk_cards)),
            "evidence_rows": int(len(risk_evidence)),
            "batch_dir": str(batch_dir),
            "model_artifact_id": model_artifact_id,
            "dry_run_rule_baseline": bool(use_rule_baseline),
        }
        self._write_run_reports(batch_dir, summary, normalize_report, feature_report, feature_parity_report, selection_report, gate_decisions, disabled_notes)
        return summary

    def _run_detectors(self, selected: pd.DataFrame, features: pd.DataFrame, gate_decisions: pd.DataFrame) -> pd.DataFrame:
        enabled = set(gate_decisions[gate_decisions["gate_status"].isin(["enabled_rule_v1", "weak_enabled_review_required"])]["detector_name"].astype(str))
        detectors = []
        if "terminal_loss_warning" in enabled:
            detectors.append(TerminalLossDetector())
        if "purchase_interval_overdue_warning" in enabled:
            detectors.append(IntervalOverdueDetector())
        if "purchase_frequency_fluctuation_warning" in enabled:
            detectors.append(FrequencyDropDetector())
        if "purchase_quantity_fluctuation_warning" in enabled:
            detectors.append(QuantityDropDetector())
        if "new_terminal_detection" in enabled:
            detectors.append(OneShotAttentionDetector())
        frames = [detector.run(selected, features) for detector in detectors]
        frames = [frame for frame in frames if not frame.empty]
        if not frames:
            return pd.DataFrame(columns=["candidate_id", "detector_name", "hit_flag", "severity", "confidence", "evidence_type", "reason_code", "metric_name", "metric_value", "visibility_level", "caveat", "forbidden_claims"])
        return pd.concat(frames, ignore_index=True)

    def _write_run_reports(
        self,
        batch_dir: Path,
        summary: dict[str, Any],
        normalize_report: pd.DataFrame,
        feature_report: pd.DataFrame,
        feature_parity_report: pd.DataFrame,
        selection_report: pd.DataFrame,
        gate_decisions: pd.DataFrame,
        disabled_notes: pd.DataFrame,
    ) -> None:
        (batch_dir / "run_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
        (batch_dir / "run_summary.md").write_text(
            "\n".join(
                [
                    "# Monthly Risk Algorithm Run Summary",
                    "",
                    f"- report_month: {summary['report_month']}",
                    f"- cutoff_date: {summary['cutoff_date']}",
                    f"- entity_rows: {summary['entity_rows']}",
                    f"- feature_rows: {summary['feature_rows']}",
                    f"- selected_candidate_rows: {summary['selected_candidate_rows']}",
                    f"- batch_dir: {summary['batch_dir']}",
                    f"- dry_run_rule_baseline: {summary['dry_run_rule_baseline']}",
                ]
            ),
            encoding="utf-8",
        )
        normalize_report.to_csv(batch_dir / "normalization_report.csv", index=False)
        feature_report.to_csv(batch_dir / "feature_quality_report.csv", index=False)
        feature_parity_report.to_csv(batch_dir / "feature_parity_runtime_report.csv", index=False)
        selection_report.to_csv(batch_dir / "selection_report.csv", index=False)
        gate_decisions.to_csv(batch_dir / "detector_quality_gate.csv", index=False)
        disabled_notes.to_csv(batch_dir / "disabled_detector_notes.csv", index=False)
