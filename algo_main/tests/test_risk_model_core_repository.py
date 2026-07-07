from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_BATCH = REPO_ROOT / "tests" / "fixtures" / "risk_result_batch_minimal"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_parquet_repository_reads_csv_fixture_tables() -> None:
    from risk_model_core import ParquetRiskResultRepository

    repo = ParquetRiskResultRepository(FIXTURE_BATCH)

    assert repo.manifest().batch_id == "fixture-monthly-v1"
    assert repo.manifest().report_type == "monthly"
    assert repo.manifest().auto_dispatch_allowed is False
    assert repo.manifest().customer_facing_probability_service_allowed is False

    entities = repo.list_risk_entities()
    assert len(entities) == 2
    assert repo.get_risk_entity("re_1")["candidate_id"] == "c1"
    assert len(repo.list_risk_cards("re_1")) == 1
    assert len(repo.list_evidence("rc_1")) == 1
    assert repo.list_timeline("re_1").iloc[0]["risk_entity_id"] == "re_1"
    assert len(repo.list_hospital_aggregates()) == 1
    assert len(repo.list_drug_aggregates()) == 1
    assert repo.list_monthly_reports().iloc[0]["monthly_report_id"] == "monthly_fixture"
    assert len(repo.list_proof_cases()) == 0
    assert repo.get_page_payload("index_payload")["page_title"] == "Monthly workbench"


def test_services_work_over_repository() -> None:
    from risk_model_core import ParquetRiskResultRepository, ProofCaseService, ReportService, RiskCardService, RiskQueryService

    repo = ParquetRiskResultRepository(FIXTURE_BATCH)

    detail = RiskQueryService(repo).get_detail("re_1")
    assert detail["entity"]["risk_entity_id"] == "re_1"
    assert detail["cards"][0]["risk_card_id"] == "rc_1"

    cards = RiskCardService(repo).list_cards_with_copy("re_1")
    assert cards[0]["safe_summary"]
    assert cards[0]["suggested_action"]

    reports = ReportService(repo).list_reports()
    assert reports[0]["report_type"] == "monthly"
    assert ReportService(repo).monthly_dashboard()["page_title"] == "Monthly management dashboard"
    assert ProofCaseService(repo).list_proof_cases() == []
