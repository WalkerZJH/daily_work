from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "front_end"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_static_pages_are_vue_mount_shells_for_duplicate_demo_pages() -> None:
    for page in ["index.html", "dashboard.html", "clues.html", "clue-detail.html", "oneshot.html", "backtest.html"]:
        text = read(FRONTEND / page)
        assert '<div id="app"></div>' in text
        assert 'src="/src/main.js"' in text or 'src=\"/src/main.js\"' in text
        assert "app.js" not in text


def test_navigation_uses_monthly_risk_and_daily_rule_clue_positioning() -> None:
    for path in [FRONTEND / "layout" / "layout.js", FRONTEND / "src" / "layout" / "navigation.js"]:
        text = read(path)
        assert "index.html" in text
        assert "clues.html" in text
        assert "今日规则线索" in text
        assert "新进终端监测" in text
        assert "algo-architecture.html" in text
        assert "全部风险线索" not in text
        assert "风险实体清单" not in text


def test_vue_routes_keep_vue_version_as_canonical_demo_pages() -> None:
    text = read(FRONTEND / "src" / "App.vue")
    for term in [
        "MonthlyWorkbenchView",
        "RiskEntityListView",
        "RiskEntityDetailView",
        "MonthlyReportView",
        "ProofCaseView",
        "OneshotMonitorView",
        "今日规则线索",
        "规则线索详情",
    ]:
        assert term in text


def test_workbench_surfaces_monthly_risk_plus_daily_detector_summary() -> None:
    text = read(FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue")
    for term in [
        "月报高风险工作台",
        "Monthly Risk + Daily Rule Inspection",
        "今日规则巡检摘要",
        "今日规则线索",
        "已附着规则证据",
        "detectorCatalogSummary",
        "detectorConfigStatus.message",
        "月报丢失概率",
        "损失价值",
        "workbenchDisplayRows",
    ]:
        assert term in text
    assert "模型关键指标" not in text
    assert "业务评分" not in text


def test_clues_page_is_rule_clue_pool_and_distinguishes_source_types() -> None:
    text = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityListView.vue")
    for term in [
        "今日规则线索",
        "全部规则线索",
        "月报高风险对象",
        "仅规则命中",
        "规则巡检分",
        "isMonthlyHighRiskEntity",
        "detailHref",
        "dailyDetectorStatus",
    ]:
        assert term in text
    assert "模型高风险" not in text
    assert "detector 风险概率" not in text


def test_detail_page_supports_monthly_entity_and_detector_only_modes() -> None:
    text = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityDetailView.vue")
    for term in [
        "isMonthlyHighRiskEntity",
        "月报风险与规则证据",
        "规则线索详情",
        "仅规则命中对象",
        "detectorEvidence",
        "规则巡检分",
        "probabilityTrend",
        "reportMonth",
        "riskProbabilityText",
        "损失价值",
    ]:
        assert term in text
    assert "detectorScore" in text
    assert "detector 概率" not in text


def test_demo_data_uses_new_rule_clue_view_model() -> None:
    text = read(FRONTEND / "src" / "modules" / "monthly-demo" / "demoData.js")
    for term in [
        "dailyDetectorStatus",
        "detectorCatalogSummary",
        "detectorConfigStatus",
        "dailyDetectorClues",
        "sourceType: 'monthly_high_risk'",
        "sourceType: 'daily_rule_clue'",
        "sourceTypeLabel: '月报高风险对象'",
        "sourceTypeLabel: '仅规则命中'",
        "detectorScoreLabel: '规则巡检分'",
        "lossValue",
        "probabilityTrendByEntityId",
    ]:
        assert term in text


def test_watchlist_page_is_removed_and_workbench_keeps_twenty_slot_fill_policy() -> None:
    assert not (FRONTEND / "watchlist.html").exists()
    assert not (FRONTEND / "src" / "modules" / "risk-worklist" / "ObservationWatchlistView.vue").exists()

    for path in [
        FRONTEND / "src" / "App.vue",
        FRONTEND / "src" / "layout" / "navigation.js",
        FRONTEND / "layout" / "layout.js",
        FRONTEND / "vite.config.js",
    ]:
        text = read(path)
        assert "watchlist.html" not in text
        assert "ObservationWatchlistView" not in text

    data = read(FRONTEND / "src" / "modules" / "monthly-demo" / "demoData.js")
    workbench = read(FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue")
    for term in [
        "workbenchTargetCount: 20",
        "globalCurrentMonthHospitalDrugCount",
        "workbenchFillCandidates",
        "workbenchDisplayRows",
        "manufacturer",
        "hospitalDrugKey",
        "fillSource",
    ]:
        assert term in data or term in workbench


def test_internal_algorithm_debug_pages_are_removed_from_user_frontend() -> None:
    assert not (FRONTEND / "algo-config.html").exists()
    assert not (FRONTEND / "algo-health.html").exists()
    assert not (FRONTEND / "src" / "modules" / "algo-config").exists()
    assert not (FRONTEND / "src" / "modules" / "algo-health").exists()

    for path in [
        FRONTEND / "src" / "App.vue",
        FRONTEND / "src" / "layout" / "navigation.js",
        FRONTEND / "layout" / "layout.js",
        FRONTEND / "vite.config.js",
    ]:
        text = read(path)
        assert "algo-config" not in text
        assert "algo-health" not in text
