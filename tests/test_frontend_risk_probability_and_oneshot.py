from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "front_end"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_monthly_risk_entities_keep_probability_and_loss_value_contract() -> None:
    data = read(FRONTEND / "src" / "modules" / "monthly-demo" / "demoData.js")
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")
    workbench = read(FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue")

    for term in [
        "riskProbability",
        "averageConsumptionInWindow",
        "lossValue",
        "lossValueText",
        "row.risk_probability * row.average_consumption_in_window",
        "loss_value",
        "monthly_loss_value",
        "月报丢失概率",
        "损失价值",
    ]:
        assert term in data or term in adapter or term in workbench

    assert "业务评分" not in workbench
    assert "business score" not in workbench.lower()


def test_detector_evidence_uses_rule_inspection_score_not_probability() -> None:
    data = read(FRONTEND / "src" / "modules" / "monthly-demo" / "demoData.js")
    detail = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityDetailView.vue")
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")

    for term in [
        "detectorResults",
        "detectorEvidence",
        "detectorScore",
        "detectorScoreText",
        "detectorScoreLabel",
        "规则巡检分",
        "rootCauseLabel",
        "evidenceText",
    ]:
        assert term in data or term in detail or term in adapter

    assert "detector 风险概率" not in detail
    assert "detector 概率" not in detail
    assert "规则概率" not in detail


def test_oneshot_new_terminal_monitoring_has_sidebar_route_and_page() -> None:
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
    assert 'src="/src/main.js"' in shell


def test_algorithm_architecture_keeps_oneshot_logic_and_customer_facing_contract() -> None:
    text = read(FRONTEND / "algo-architecture.html")

    for term in [
        "oneshot",
        "新进终端监测",
        "复购倾向",
        "首次采购",
        "损失价值",
        "每日规则巡检",
    ]:
        assert term in text

    for forbidden in [
        "business score",
        "业务评分",
        "XGBoost",
        "LightGBM",
        "CatBoost",
    ]:
        assert forbidden not in text
