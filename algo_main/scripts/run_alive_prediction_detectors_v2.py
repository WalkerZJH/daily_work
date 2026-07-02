#!/usr/bin/env python
"""Run M4 detector completion v2 evidence enhancements."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.detectors_v2 import run_detectors_v2


SURVIVAL_PATH = ROOT / "reports/alive_prediction_survival_lite_v1/survival_refinement_results.csv"
V1_EVIDENCE_PATH = ROOT / "reports/alive_prediction_detectors_v1/detector_evidence_results.csv"
OUTPUT_DIR = ROOT / "reports/alive_prediction_detectors_v2"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_inputs(dry_run: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    if dry_run:
        survival = pd.DataFrame(
            [
                {
                    "candidate_id": "m1|h1|d1|drug_code|2024-01",
                    "manufacturer_code": "m1",
                    "hospital_code": "h1",
                    "drug_group": "d1",
                    "drug_group_source": "drug_code",
                    "cutoff_month": "2024-01",
                    "horizon": "H6",
                    "churn_probability_H": 0.8,
                    "relative_business_priority_score_H": 80.0,
                    "relative_value_at_risk_H": 100.0,
                    "survival_state": "likely_churn_interval",
                    "survival_confidence": 0.8,
                    "overdue_ratio": 3.2,
                    "overdue_gap_months": 5.0,
                    "expected_interval_months": 2.0,
                    "months_since_last_purchase": 6.4,
                    "history_sufficiency_flag": "history_sufficient",
                    "demand_shape_label": "smooth",
                    "demand_shape_route": "main_probability_model",
                    "purchase_interval_mad_days_asof_cutoff": 20.0,
                    "days_since_last_purchase_asof_cutoff": 200.0,
                    "median_purchase_interval_days_asof_cutoff": 60.0,
                },
                {
                    "candidate_id": "m2|h2|d2|drug_code|2024-01",
                    "manufacturer_code": "m2",
                    "hospital_code": "h2",
                    "drug_group": "d2",
                    "drug_group_source": "drug_code",
                    "cutoff_month": "2024-01",
                    "horizon": "H6",
                    "churn_probability_H": 0.7,
                    "relative_business_priority_score_H": 70.0,
                    "relative_value_at_risk_H": 100.0,
                    "survival_state": "materially_overdue",
                    "survival_confidence": 0.3,
                    "overdue_ratio": 2.4,
                    "overdue_gap_months": 3.0,
                    "expected_interval_months": 2.0,
                    "months_since_last_purchase": 4.8,
                    "history_sufficiency_flag": "history_medium",
                    "demand_shape_label": "lumpy",
                    "demand_shape_route": "observation_only",
                },
            ]
        )
        evidence = pd.DataFrame(
            [
                {
                    "candidate_id": "m1|h1|d1|drug_code|2024-01",
                    "detector_name": "purchase_frequency_fluctuation_warning",
                    "evidence_values": '{"decay3": 0.0, "decay6": 0.25, "order12": 8}',
                },
                {
                    "candidate_id": "m2|h2|d2|drug_code|2024-01",
                    "detector_name": "purchase_frequency_fluctuation_warning",
                    "evidence_values": '{"decay3": 1.0, "decay6": 1.0, "order12": 2}',
                },
            ]
        )
        return survival, evidence
    survival = pd.read_csv(SURVIVAL_PATH) if SURVIVAL_PATH.exists() else pd.DataFrame()
    v1_evidence = pd.read_csv(V1_EVIDENCE_PATH) if V1_EVIDENCE_PATH.exists() else pd.DataFrame()
    return survival, v1_evidence


def build_summary(outputs: dict[str, pd.DataFrame]) -> str:
    interval = outputs["interval"]
    frequency = outputs["frequency"]
    combined = outputs["combined"]
    readiness = outputs["p_value_readiness"]
    d001_p = int(interval["p_value"].notna().sum()) if not interval.empty else 0
    d002_p = int(frequency["p_value"].notna().sum()) if not frequency.empty else 0
    d001_fdr = int(interval["fdr_eligible"].astype(bool).sum()) if not interval.empty else 0
    d002_fdr = int(frequency["fdr_eligible"].astype(bool).sum()) if not frequency.empty else 0
    fdr_applied_all_false = not combined["fdr_applied"].astype(bool).any() if not combined.empty else True
    d002_methods = (
        ";".join(sorted(set(frequency["p_value_method"].dropna().astype(str)))) if not frequency.empty else "missing"
    )
    return f"""# Detector V2 Summary

1. D001 purchase_interval_overdue_warning generated: {not interval.empty}
2. D002 purchase_frequency_decay_rate_test generated: {not frequency.empty}
3. D001 rows: {len(interval)}
4. D002 rows: {len(frequency)}
5. D001 hit count: {int(interval['hit_flag'].astype(bool).sum()) if not interval.empty else 0}
6. D002 hit count: {int(frequency['hit_flag'].astype(bool).sum()) if not frequency.empty else 0}
7. D001 p_value available count: {d001_p}
8. D002 p_value available count: {d002_p}
9. fdr_eligible count: {int(combined['fdr_eligible'].astype(bool).sum()) if not combined.empty else 0}
10. fdr_applied all false: {fdr_applied_all_false}
11. MAD missing impact on D001: D001 falls back to overdue_ratio evidence and is not FDR eligible when MAD is missing.
12. D002 p_value_method: {d002_methods}
13. Quantity trend implemented: false
14. SKU narrowing implemented: false
15. Wallet share implemented: false
16. Price detector implemented: false
17. Delivery detector implemented: false
18. L2/L3 implemented: false
19. Probability/business priority changed: false

## p-value Readiness

{readiness.to_markdown(index=False) if not readiness.empty else '_No p-value readiness rows._'}
"""


def build_data_quality(outputs: dict[str, pd.DataFrame], survival: pd.DataFrame, v1_evidence: pd.DataFrame) -> str:
    combined = outputs["combined"]
    notes = combined["data_quality_note"].fillna("").astype(str).value_counts().to_dict() if not combined.empty else {}
    return f"""# Detector V2 Data Quality Report

- Survival input rows: {len(survival)}
- V1 evidence input rows: {len(v1_evidence)}
- V2 output rows: {len(combined)}
- Data quality notes: {notes}
- Raw demand-shape observation table loaded: false
- Parquet feature rebuild/read used: false
"""


def build_semantics_audit() -> str:
    return """# Detector V2 Semantics Audit

- D001/D002 are evidence detectors only.
- D001/D002 do not change `churn_probability_H`.
- D001/D002 do not change `relative_business_priority_score_H`.
- D001/D002 do not change `survival_state`.
- `p_value` is not a churn probability.
- detector severity/confidence are not churn probabilities.
- D001 is only partial FDR readiness when interval MAD is missing.
- D002 can provide p_value for future FDR.
- FDR is not executed in v2; `fdr_applied` is fixed false.
- L2/L3 are not implemented.
- Delivery, price, amount trend, quantity trend, SKU narrowing, and wallet share are not implemented in v2.
- M6 cache is not implemented; evidence timeline fields are reserved only.
"""


def build_next_stage_readiness(outputs: dict[str, pd.DataFrame]) -> str:
    interval = outputs["interval"]
    frequency = outputs["frequency"]
    d001_rows = len(interval)
    d002_rows = len(frequency)
    d001_p = int(interval["p_value"].notna().sum()) if d001_rows else 0
    d002_p = int(frequency["p_value"].notna().sum()) if d002_rows else 0
    if d001_rows and d002_rows:
        status = "completed"
    elif d001_rows or d002_rows:
        status = "partial"
    else:
        status = "failed"
    if d002_p > 0 and d001_p < d001_rows:
        fdr_ready = "partial"
    elif d001_p > 0 and d002_p > 0:
        fdr_ready = "yes"
    else:
        fdr_ready = "no"
    return f"""# Detector V2 Next Stage Readiness

detector_completion_v2_status = {status}
ready_for_l2_l3_design = conditional
fdr_ready = {fdr_ready}

condition:
L2/L3 design may consider D002 p_value for future FDR readiness, but D001
remains interval-evidence only unless interval MAD is added for most rows.
"""


def write_outputs(outputs: dict[str, pd.DataFrame], survival: pd.DataFrame, v1_evidence: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs["combined"].to_csv(output_dir / "detector_evidence_results_v2.csv", index=False)
    outputs["interval"].to_csv(output_dir / "detector_interval_overdue_results.csv", index=False)
    outputs["frequency"].to_csv(output_dir / "detector_frequency_rate_test_results.csv", index=False)
    outputs["family_summary"].to_csv(output_dir / "detector_v2_family_summary.csv", index=False)
    outputs["p_value_readiness"].to_csv(output_dir / "detector_v2_p_value_readiness_report.csv", index=False)
    write_text(output_dir / "detector_v2_summary.md", build_summary(outputs))
    write_text(output_dir / "detector_v2_semantics_audit.md", build_semantics_audit())
    write_text(output_dir / "detector_v2_data_quality_report.md", build_data_quality(outputs, survival, v1_evidence))
    write_text(output_dir / "detector_v2_next_stage_readiness.md", build_next_stage_readiness(outputs))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Run against a tiny fixture.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    survival, v1_evidence = load_inputs(dry_run=args.dry_run)
    outputs = run_detectors_v2(survival, v1_evidence)
    output_dir = OUTPUT_DIR if not args.dry_run else OUTPUT_DIR / "_dry_run"
    write_outputs(outputs, survival, v1_evidence, output_dir)
    print(f"output_dir={output_dir}")
    print(f"D001_rows={len(outputs['interval'])}")
    print(f"D001_hits={int(outputs['interval']['hit_flag'].astype(bool).sum()) if not outputs['interval'].empty else 0}")
    print(f"D002_rows={len(outputs['frequency'])}")
    print(f"D002_hits={int(outputs['frequency']['hit_flag'].astype(bool).sum()) if not outputs['frequency'].empty else 0}")


if __name__ == "__main__":
    main()
