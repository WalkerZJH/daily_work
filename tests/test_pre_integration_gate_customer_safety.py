import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = (
    ROOT
    / "algo_main"
    / "data"
    / "entity_complete_v2_coverage_expansion"
    / "13_formal_algorithm_core_raw_to_batch"
    / "formal_result_batches"
    / "report_month=2025-12"
    / "batch_id=2025-12-monthly-risk-algorithm-formal-v2-raw"
)
REPORT_DIR = ROOT / "algo_main" / "reports" / "entity_complete_v2_coverage_expansion" / "20_pre_frontend_backend_integration_gate"

FORBIDDEN_TEXT = [
    "AUC",
    "ECE",
    "PR-AUC",
    "LogLoss",
    "Brier",
    "XGBoost",
    "LightGBM",
    "CatBoost",
    "feature ablation",
    "leakage audit",
    "FDR",
    "Theil-Sen",
    "CUSUM",
    "\u7ade\u54c1\u66ff\u4ee3\u8ff9\u8c61\u660e\u663e",
    "\u653f\u7b56\u843d\u6807\u5df2\u786e\u8ba4",
    "\u914d\u9001\u5546\u8d23\u4efb\u5df2\u786e\u8ba4",
    "\u533b\u9662\u786e\u5b9a\u6d41\u5931",
    "\u4e00\u5b9a\u4e0d\u4f1a\u518d\u91c7\u8d2d",
    "\u81ea\u52a8\u6d3e\u5355",
]


def test_result_batch_customer_visible_text_has_no_forbidden_claims() -> None:
    cards = pd.read_csv(BATCH_DIR / "risk_cards.csv")
    evidence = pd.read_csv(BATCH_DIR / "risk_card_evidence.csv")
    text_blob = "\n".join(
        [
            "\n".join(cards.get(col, pd.Series(dtype=str)).dropna().astype(str).tolist())
            for col in ["card_title", "card_summary", "suggested_action"]
        ]
        + ["\n".join(evidence.get("evidence_text", pd.Series(dtype=str)).dropna().astype(str).tolist())]
    )
    assert not [token for token in FORBIDDEN_TEXT if token in text_blob]


def test_safety_flags_for_one_shot_observation_and_dispatch() -> None:
    entities = pd.read_csv(BATCH_DIR / "risk_entities.csv")
    manifest = json.loads((BATCH_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert not entities["auto_dispatch_allowed"].astype(bool).any()
    assert manifest["customer_facing_probability_service_allowed"] is False
    one_shot = entities[entities["is_one_shot"].astype(bool)]
    assert (one_shot["probability_display_mode"] == "hide_probability").all()
    observation = entities[entities["is_observation"].astype(bool)]
    assert not observation["is_high_risk"].astype(bool).any()


def test_customer_safety_gate_is_ready() -> None:
    review = (REPORT_DIR / "safety_and_customer_visibility_review.md").read_text(encoding="utf-8")
    assert "- gate: READY" in review
    assert "distributor responsibility confirmed: false" in review
