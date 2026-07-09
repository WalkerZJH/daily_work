from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "front_end"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_frontend_backend_api_exposes_monthly_and_daily_detector_contracts() -> None:
    text = read(FRONTEND / "src" / "services" / "backendApi.js")

    for term in [
        "getWorkbench()",
        "getRiskEntities(params)",
        "getRiskEntityDetail(entityId)",
        "getDetectorCatalog()",
        "getDetectorRuns(params = {})",
        "getDetectorClues(params = {})",
        "getDailyDetectorStatus()",
        "getDailyDetectorClues(params = {})",
        "getRiskEntityDetectorEvidence(riskEntityId, params = {})",
        "getDetectorConfigStatus()",
        "getMonthlyReports()",
        "/api/v1/workbench",
        "/api/v1/daily-detector/status",
        "/api/v1/daily-detector/clues",
        "/api/v1/detectors/catalog",
        "/api/v1/detectors/config-status",
        "/detector-evidence",
    ]:
        assert term in text


def test_page_adapter_normalizes_view_model_and_fallback_boundaries() -> None:
    text = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")

    for term in [
        "loadWorkbenchData",
        "loadRuleCluesData",
        "loadClueDetailData",
        "tryLoadDailyDetectorContext",
        "tryLoadDailyDetectorClues",
        "displayLookupStatus",
        "loss_value",
        "monthly_loss_value",
        "business_score",
        "riskProbability",
        "lossValue",
        "detectorScore",
        "detectorScoreLabel",
        "sourceType: isMonthly ? 'monthly_high_risk' : 'daily_rule_clue'",
        "规则巡检分",
    ]:
        assert term in text

    for forbidden in [
        "readFile",
        "parquet",
        "csv",
        "algo_main",
        "daily_work/prototype",
    ]:
        assert forbidden not in text


def test_integration_note_records_connected_and_fallback_interfaces() -> None:
    note = FRONTEND / "docs" / "monthly_risk_daily_detector_frontend_integration.md"
    assert note.exists()
    text = read(note)

    for term in [
        "GET /api/v1/detectors/catalog",
        "GET /api/v1/detectors/runs",
        "GET /api/v1/detectors/clues",
        "GET /api/v1/daily-detector/status",
        "GET /api/v1/daily-detector/clues",
        "GET /api/v1/risk-entities/{risk_entity_id}/detector-evidence",
        "GET /api/v1/detectors/config-status",
        "Fallback behavior",
        "ready=false",
        "timeout",
        "network failure",
        "demo/mock",
    ]:
        assert term in text


def test_frontend_mock_data_matches_detector_semantics() -> None:
    text = read(FRONTEND / "src" / "modules" / "monthly-demo" / "demoData.js")

    assert "riskProbability" in text
    assert "detectorScoreLabel: '规则巡检分'" in text
    assert "lossValue" in text
    assert "sourceTypeLabel: '月报高风险对象'" in text
    assert "sourceTypeLabel: '仅规则命中'" in text
    assert "businessScore" in text
    assert "业务评分" not in text
