from __future__ import annotations

from pathlib import Path
import json

import pandas as pd


BATCH_DIR = Path("data/entity_complete_v2_coverage_expansion/10_frontend_worklist_model_package/risk_result_batches/batch_id=2025-12-frontend-worklist-v1")


def test_generated_page_payloads_exist() -> None:
    payload_dir = BATCH_DIR / "page_payloads"

    for name in [
        "index_payload.json",
        "clues_payload.json",
        "watchlist_payload.json",
        "dashboard_payload.json",
        "backtest_payload.json",
        "verify_payload.json",
        "distributor_payload.json",
        "order_detail_sample_payload.json",
        "monthly_report_payload.json",
    ]:
        assert (payload_dir / name).exists()

    assert len(list((payload_dir / "clue_detail_samples").glob("*.json"))) >= 1


def test_customer_payloads_have_safe_boundaries() -> None:
    payload_dir = BATCH_DIR / "page_payloads"
    forbidden = ["AUC", "ECE", "XGBoost", "FDR", "MK显著", "Theil-Sen", "CUSUM", "竞品替代迹象明显", "配送商责任已确认", "医院确定流失", "一定不会再采购", "自动派单"]

    for path in payload_dir.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        for term in forbidden:
            assert term not in text


def test_distributor_and_dashboard_payloads_do_not_overclaim() -> None:
    payload_dir = BATCH_DIR / "page_payloads"
    distributor = json.loads((payload_dir / "distributor_payload.json").read_text(encoding="utf-8"))
    dashboard = json.loads((payload_dir / "dashboard_payload.json").read_text(encoding="utf-8"))

    assert distributor["delivery_detector_enabled"] is False
    assert distributor["alerts"] == []
    assert "待接入工单反馈" in dashboard["kpi_cards"]["recovery_roi"]


def test_generated_entities_keep_semantic_boundaries() -> None:
    entities = pd.read_parquet(BATCH_DIR / "risk_entities.parquet", columns=["is_one_shot", "is_observation", "palive_display", "is_high_risk", "auto_dispatch_allowed"])

    assert entities["auto_dispatch_allowed"].eq(False).all()
    assert entities.loc[entities["is_one_shot"], "palive_display"].eq("不展示").all()
    assert entities.loc[entities["is_observation"], "is_high_risk"].eq(False).all()
