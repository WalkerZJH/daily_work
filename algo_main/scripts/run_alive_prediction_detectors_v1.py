#!/usr/bin/env python
"""Run M4 detector evidence prototype for alive prediction candidates."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.detectors import (
    enrich_with_features,
    family_summary,
    interface_only_detectors,
    new_terminal_detection,
    purchase_frequency_fluctuation_warning,
    purchase_quantity_fluctuation_warning,
    terminal_loss_warning,
)


SURVIVAL_PATH = ROOT / "reports/alive_prediction_survival_lite_v1/survival_refinement_results.csv"
ONE_SHOT_PATH = ROOT / "reports/alive_prediction_candidate_pool_v1/one_shot_attention_candidates.csv"
FEATURE_PATH = ROOT / "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/cutoff_2024-01_2024-12/feature_table__status0.parquet"
OUTPUT_DIR = ROOT / "reports/alive_prediction_detectors_v1"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def md_table(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df is None or df.empty:
        return "_No rows._"
    return df.head(max_rows).to_markdown(index=False)


def load_survival(dry_run: bool = False) -> pd.DataFrame:
    if dry_run:
        return pd.DataFrame(
            [
                {
                    "candidate_id": "m1|h1|d1|drug_code|2024-01",
                    "manufacturer_code": "m1",
                    "hospital_code": "h1",
                    "drug_group": "d1",
                    "drug_group_source": "drug_code",
                    "cutoff_month": "2024-01",
                    "horizon": 6,
                    "churn_probability_H": 0.8,
                    "relative_business_priority_score_H": 80.0,
                    "relative_value_at_risk_H": 100.0,
                    "survival_state": "likely_churn_interval",
                    "survival_confidence": 0.8,
                    "overdue_ratio": 3.2,
                    "overdue_gap_months": 5.0,
                    "expected_interval_months": 2.0,
                    "history_sufficiency_flag": "history_sufficient",
                    "demand_shape_label": "smooth",
                    "demand_shape_route": "main_probability_model",
                },
                {
                    "candidate_id": "m2|h2|d2|drug_code|2024-01",
                    "manufacturer_code": "m2",
                    "hospital_code": "h2",
                    "drug_group": "d2",
                    "drug_group_source": "drug_code",
                    "cutoff_month": "2024-01",
                    "horizon": 6,
                    "churn_probability_H": 0.7,
                    "relative_business_priority_score_H": 70.0,
                    "relative_value_at_risk_H": 100.0,
                    "survival_state": "materially_overdue",
                    "survival_confidence": 0.3,
                    "overdue_ratio": 2.4,
                    "overdue_gap_months": 3.0,
                    "expected_interval_months": 2.0,
                    "history_sufficiency_flag": "history_medium",
                    "demand_shape_label": "lumpy",
                    "demand_shape_route": "observation_only",
                },
            ]
        )
    return pd.read_csv(SURVIVAL_PATH) if SURVIVAL_PATH.exists() else pd.DataFrame()


def load_features(dry_run: bool = False) -> pd.DataFrame | None:
    if dry_run:
        return pd.DataFrame(
            [
                {
                    "manufacturer_code": "m1",
                    "hospital_code": "h1",
                    "drug_group": "d1",
                    "drug_group_source": "drug_code",
                    "cutoff_month": "2024-01",
                    "order_count_last_1m_asof_cutoff": 0,
                    "order_count_last_3m_asof_cutoff": 0,
                    "order_count_last_6m_asof_cutoff": 1,
                    "order_count_last_12m_asof_cutoff": 8,
                    "purchase_quantity_sum_last_1m_asof_cutoff": 0,
                    "purchase_quantity_sum_last_3m_asof_cutoff": 3,
                    "purchase_quantity_sum_last_6m_asof_cutoff": 8,
                    "historical_avg_monthly_quantity_asof_cutoff": 10,
                    "historical_median_monthly_quantity_asof_cutoff": 8,
                    "purchase_count_asof_cutoff": 8,
                    "active_month_count_asof_cutoff": 5,
                    "months_observed_asof_cutoff": 12,
                    "first_purchase_month": "2023-01",
                },
                {
                    "manufacturer_code": "m2",
                    "hospital_code": "h2",
                    "drug_group": "d2",
                    "drug_group_source": "drug_code",
                    "cutoff_month": "2024-01",
                    "order_count_last_1m_asof_cutoff": 0,
                    "order_count_last_3m_asof_cutoff": 0,
                    "order_count_last_6m_asof_cutoff": 0,
                    "order_count_last_12m_asof_cutoff": 2,
                    "purchase_quantity_sum_last_1m_asof_cutoff": 0,
                    "purchase_quantity_sum_last_3m_asof_cutoff": 0,
                    "purchase_quantity_sum_last_6m_asof_cutoff": 0,
                    "historical_avg_monthly_quantity_asof_cutoff": 10,
                    "historical_median_monthly_quantity_asof_cutoff": 8,
                    "purchase_count_asof_cutoff": 2,
                    "active_month_count_asof_cutoff": 1,
                    "months_observed_asof_cutoff": 10,
                    "first_purchase_month": "2023-01",
                },
            ]
        )
    if not FEATURE_PATH.exists():
        return None
    cols = [
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "cutoff_month",
        "order_count_last_1m_asof_cutoff",
        "order_count_last_3m_asof_cutoff",
        "order_count_last_6m_asof_cutoff",
        "order_count_last_12m_asof_cutoff",
        "purchase_quantity_sum_last_1m_asof_cutoff",
        "purchase_quantity_sum_last_3m_asof_cutoff",
        "purchase_quantity_sum_last_6m_asof_cutoff",
        "historical_avg_monthly_quantity_asof_cutoff",
        "purchase_count_asof_cutoff",
        "active_month_count_asof_cutoff",
        "months_observed_asof_cutoff",
        "first_purchase_month",
    ]
    df = pd.read_parquet(FEATURE_PATH, columns=cols)
    df["drug_group_source"] = "drug_code"
    return df


def load_one_shot(dry_run: bool = False) -> pd.DataFrame | None:
    if dry_run:
        return pd.DataFrame(
            [
                {
                    "manufacturer_code": "m3",
                    "hospital_code": "h3",
                    "drug_group": "d3",
                    "drug_group_source": "drug_code",
                    "first_purchase_month": "2024-01",
                    "one_shot_value_score": 100.0,
                }
            ]
        )
    return pd.read_csv(ONE_SHOT_PATH) if ONE_SHOT_PATH.exists() else None


def semantics_audit_text() -> str:
    return "\n".join(
        [
            "# Detector Semantics Audit",
            "",
            "- detector severity is not a probability.",
            "- detector confidence is not a probability.",
            "- detectors do not change `churn_probability_H`.",
            "- detectors do not change `relative_business_priority_score_H`.",
            "- `terminal_loss_warning` cannot be interpreted as hospital confirmed churn or confirmed non-purchase.",
            "- frequency and quantity detectors only indicate recent purchase frequency/quantity abnormal changes.",
            "- price detectors are interface-only in v1.",
            "- delivery response detectors are interface-only in v1.",
            "- M6 evidence cache fields are reserved only; cache is not implemented.",
        ]
    )


def data_quality_text(survival: pd.DataFrame, enriched: pd.DataFrame, evidence: pd.DataFrame) -> str:
    missing_cols = [
        c
        for c in [
            "order_count_last_3m_asof_cutoff",
            "order_count_last_6m_asof_cutoff",
            "order_count_last_12m_asof_cutoff",
            "purchase_quantity_sum_last_3m_asof_cutoff",
            "historical_avg_monthly_quantity_asof_cutoff",
        ]
        if c not in enriched.columns
    ]
    return "\n".join(
        [
            "# Detector Data Quality Report",
            "",
            f"- survival input rows: {len(survival)}",
            f"- detector evidence rows: {len(evidence)}",
            f"- missing feature columns: {', '.join(missing_cols) if missing_cols else 'none'}",
            f"- not_evaluable evidence rows: {int(evidence['data_quality_status'].eq('not_evaluable').sum()) if not evidence.empty else 0}",
            "",
            "Price and delivery-response detectors are interface-only by design in v1.",
        ]
    )


def next_stage_text(summary: pd.DataFrame) -> str:
    terminal_ok = bool(
        ((summary["detector_name"].eq("terminal_loss_warning")) & (summary["detector_status"].eq("implemented"))).any()
    )
    frequency_ok = bool(
        ((summary["detector_name"].eq("purchase_frequency_fluctuation_warning")) & (summary["detector_status"].eq("implemented"))).any()
    )
    ready = "partial" if terminal_ok and frequency_ok else "no"
    proceed = "conditional" if ready == "partial" else "no"
    return "\n".join(
        [
            "# Detector Next Stage Readiness",
            "",
            f"proceed_to_M5 = {proceed}",
            f"detector_ready = {ready}",
            "m6_cache_implemented = false",
            "",
            "condition: M5 can only use implemented detector evidence and must not treat interface-only detectors as effective evidence.",
        ]
    )


def summary_text(evidence: pd.DataFrame, summary: pd.DataFrame, new_terminal_executed: bool) -> str:
    hit_counts = evidence.groupby("detector_name")["hit_flag"].sum().reset_index(name="hit_count") if not evidence.empty else pd.DataFrame()
    return "\n".join(
        [
            "# Detector v1 Summary",
            "",
            "M4 detector evidence prototype ran on M3 survival-lite recurring candidates plus optional one-shot new-terminal fact detector. It did not change probability or business-priority scores.",
            "",
            f"- detector_evidence_results rows: {len(evidence)}",
            f"- new_terminal_detection executed: {str(new_terminal_executed).lower()}",
            "",
            "## Hit Counts",
            md_table(hit_counts),
            "",
            "## Family Summary",
            md_table(summary),
            "",
            "Price warning and delivery response detectors are interface-only in v1.",
        ]
    )


def run(*, output_dir: Path = OUTPUT_DIR, dry_run: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    survival = load_survival(dry_run=dry_run)
    if survival.empty:
        empty = pd.DataFrame()
        for name in [
            "detector_evidence_results.csv",
            "detector_family_summary.csv",
            "detector_terminal_dynamic_results.csv",
            "detector_sales_fluctuation_results.csv",
            "detector_interface_only_results.csv",
        ]:
            empty.to_csv(output_dir / name, index=False)
        write_text(output_dir / "detector_v1_summary.md", "# Detector v1 Summary\n\nSkipped: survival_refinement_results missing.\n")
        write_text(output_dir / "detector_data_quality_report.md", "# Detector Data Quality Report\n\nSkipped.\n")
        write_text(output_dir / "detector_semantics_audit.md", semantics_audit_text())
        write_text(output_dir / "detector_next_stage_readiness.md", "# Detector Next Stage Readiness\n\nproceed_to_M5 = no\n")
        return
    features = load_features(dry_run=dry_run)
    enriched = enrich_with_features(survival, features)
    terminal = terminal_loss_warning(enriched)
    frequency = purchase_frequency_fluctuation_warning(enriched)
    quantity = purchase_quantity_fluctuation_warning(enriched)
    one_shot = load_one_shot(dry_run=dry_run)
    new_terminal = new_terminal_detection(one_shot)
    interface = interface_only_detectors()
    evidence = pd.concat([terminal, frequency, quantity, new_terminal, interface], ignore_index=True)
    summary = family_summary(evidence, input_row_count=len(survival))

    evidence.to_csv(output_dir / "detector_evidence_results.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(output_dir / "detector_family_summary.csv", index=False, encoding="utf-8-sig")
    pd.concat([terminal, new_terminal], ignore_index=True).to_csv(
        output_dir / "detector_terminal_dynamic_results.csv", index=False, encoding="utf-8-sig"
    )
    pd.concat([frequency, quantity], ignore_index=True).to_csv(
        output_dir / "detector_sales_fluctuation_results.csv", index=False, encoding="utf-8-sig"
    )
    interface.to_csv(output_dir / "detector_interface_only_results.csv", index=False, encoding="utf-8-sig")
    write_text(output_dir / "detector_semantics_audit.md", semantics_audit_text())
    write_text(output_dir / "detector_data_quality_report.md", data_quality_text(survival, enriched, evidence))
    write_text(output_dir / "detector_next_stage_readiness.md", next_stage_text(summary))
    write_text(output_dir / "detector_v1_summary.md", summary_text(evidence, summary, new_terminal_executed=not new_terminal.empty))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="run on a small synthetic fixture")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    run(output_dir=args.output_dir, dry_run=args.dry_run)
