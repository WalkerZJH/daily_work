from pathlib import Path


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


def test_model_core_repository_and_services_read_formal_batch() -> None:
    from risk_model_core.repositories import ParquetRiskResultRepository
    from risk_model_core.services import ProofCaseService, ReportService, RiskCardService, RiskQueryService

    repo = ParquetRiskResultRepository(BATCH_DIR)
    entities = repo.list_risk_entities()
    assert len(entities) > 0
    entity_id = str(entities.iloc[0]["risk_entity_id"])
    detail = RiskQueryService(repo).get_detail(entity_id)
    cards = RiskCardService(repo).list_cards_with_copy(entity_id)
    reports = ReportService(repo).list_reports()
    proof_cases = ProofCaseService(repo).list_proof_cases()
    assert detail
    assert len(cards) > 0
    assert len(reports) > 0
    assert proof_cases is not None


def test_model_core_smoke_summary_records_no_algo_dependency() -> None:
    review = (
        ROOT
        / "algo_main"
        / "reports"
        / "entity_complete_v2_coverage_expansion"
        / "20_pre_frontend_backend_integration_gate"
        / "model_core_service_review.md"
    ).read_text(encoding="utf-8")
    assert "algo_main import required: false" in review
    assert "M closure direct reads required: false" in review
