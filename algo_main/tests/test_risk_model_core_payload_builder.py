from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_BATCH = REPO_ROOT / "tests" / "fixtures" / "risk_result_batch_minimal"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_page_payload_builder_reads_standard_payloads() -> None:
    from risk_model_core import ParquetRiskResultRepository
    from risk_model_core.page_payload_builder import PagePayloadBuilder

    builder = PagePayloadBuilder(ParquetRiskResultRepository(FIXTURE_BATCH))

    assert builder.build_index_payload()["page_title"] == "Monthly workbench"
    assert len(builder.build_clues_payload()["items"]) == 2
    assert len(builder.build_watchlist_payload()["items"]) == 1
    assert builder.build_dashboard_payload()["kpi_cards"]["recovery_roi"] == "pending feedback integration"


def test_page_payload_builder_constructs_detail_payload() -> None:
    from risk_model_core import ParquetRiskResultRepository
    from risk_model_core.page_payload_builder import PagePayloadBuilder

    builder = PagePayloadBuilder(ParquetRiskResultRepository(FIXTURE_BATCH))
    detail = builder.build_clue_detail_payload("re_1")

    assert detail["risk_entity"]["risk_entity_id"] == "re_1"
    assert detail["risk_cards"][0]["risk_card_id"] == "rc_1"
    assert detail["risk_cards"][0]["evidence"][0]["evidence_id"] == "ev_1"
    assert detail["auto_dispatch_allowed"] is False


def test_reserved_payloads_do_not_enable_forbidden_services() -> None:
    from risk_model_core import ParquetRiskResultRepository
    from risk_model_core.page_payload_builder import PagePayloadBuilder

    builder = PagePayloadBuilder(ParquetRiskResultRepository(FIXTURE_BATCH))

    assert builder.build_backtest_payload()["proof_case_report_allowed"] is False
    assert builder.build_verify_payload()["verification_enabled"] is False
    assert builder.build_distributor_payload()["delivery_detector_enabled"] is False
