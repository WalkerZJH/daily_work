from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "front_end"
NOTES = ROOT / "daily_work" / "notes"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_risk_entities_expose_probability_business_score_and_sorted_worklist():
    data = read(FRONTEND / "src" / "modules" / "monthly-demo" / "demoData.js")
    list_page = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityListView.vue")
    workbench = read(FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue")

    for term in [
        "riskProbability",
        "averageConsumptionInWindow",
        "businessScore",
        "风险概率",
        "预测窗口内平均消费金额",
        "概率 × 预测窗口内平均消费金额",
    ]:
        assert term in data or term in list_page or term in workbench

    assert "sortedRiskEntities" in list_page
    assert "businessScore" in list_page
    assert "toLocaleString" in list_page
    assert "排序" in list_page


def test_entity_detail_displays_all_detector_results_and_reserved_aggregation_slots():
    data = read(FRONTEND / "src" / "modules" / "monthly-demo" / "demoData.js")
    detail = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityDetailView.vue")

    for term in [
        "detectorResults",
        "采购间隔 detector",
        "频次下降 detector",
        "品规收缩 detector",
        "配送履约 detector",
        "XGBoost SHAP",
        "detector 结果自然语言聚合",
        "自然语言聚合",
    ]:
        assert term in data or term in detail

    assert "v-for=\"detector in activeRiskCard.detectorResults\"" in detail
    assert "detector.score" in detail
    assert "detector.signal" in detail


def test_oneshot_new_terminal_monitoring_has_sidebar_route_and_page():
    app = read(FRONTEND / "src" / "App.vue")
    nav = read(FRONTEND / "src" / "layout" / "navigation.js")
    static_nav = read(FRONTEND / "layout" / "layout.js")
    vite = read(FRONTEND / "vite.config.js")
    page = read(FRONTEND / "src" / "modules" / "oneshot-monitor" / "OneshotMonitorView.vue")
    data = read(FRONTEND / "src" / "modules" / "monthly-demo" / "demoData.js")

    for text in [app, nav, static_nav, vite]:
        assert "oneshot.html" in text

    for term in [
        "新进终端监测",
        "oneshot",
        "复购倾向",
        "首次采购",
        "本期新进终端",
        "repurchasePropensity",
        "OneshotMonitorView",
    ]:
        assert term in page or term in data or term in app or term in nav

    shell = read(FRONTEND / "oneshot.html")
    assert '<div id="app"></div>' in shell
    assert 'src="/src/main.js"' in shell or 'src="/src/main.js"' in shell


def test_algorithm_architecture_documents_oneshot_logic_and_effect():
    text = read(FRONTEND / "algo-architecture.html")

    for term in [
        "oneshot 复购倾向计算",
        "新进终端监测",
        "首次采购后复购倾向",
        "首采金额",
        "首采后天数",
        "复购倾向分层",
        "复购促进优先级",
    ]:
        assert term in text


def test_backend_interface_note_documents_frontend_contracts():
    note = NOTES / "frontend_backend_contract_risk_probability_oneshot.md"
    assert note.exists()
    text = read(note)

    for term in [
        "RiskEntity",
        "risk_probability",
        "average_consumption_in_window",
        "business_score",
        "detector_results",
        "xgboost_shap",
        "detector_narrative",
        "oneshot",
        "repurchase_propensity",
        "GET /api/v1/risk-entities",
        "GET /api/v1/risk-entities/{entity_id}/detectors",
        "GET /api/v1/oneshot-terminals",
    ]:
        assert term in text
