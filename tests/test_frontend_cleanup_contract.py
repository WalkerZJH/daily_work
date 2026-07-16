from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "front_end"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_vite_pages_exist_without_legacy_static_assets() -> None:
    vite_pages = [
        "index.html",
        "dashboard.html",
        "clues.html",
        "clue-detail.html",
        "oneshot.html",
        "backtest.html",
        "algo-architecture.html",
        "algo-config.html",
        "verify.html",
        "distributor.html",
        "order-detail.html",
    ]
    removed_assets = ["app.js", "styles.css", "layout/layout.js"]

    for relative_path in removed_assets:
        assert not (FRONTEND / relative_path).exists()

    for page in vite_pages:
        html = read(FRONTEND / page)
        assert '<div id="app"></div>' in html
        assert 'src="/src/main.js"' in html or 'src=\"/src/main.js\"' in html
        assert "app.js" not in html
        assert "styles.css" not in html

    vite_config = read(FRONTEND / "vite.config.js")
    for page in vite_pages:
        assert page in vite_config


def test_navigation_separates_customer_pages_from_internal_pages() -> None:
    navigation = read(FRONTEND / "src" / "layout" / "navigation.js")

    for customer_page in ["index.html", "clues.html", "oneshot.html"]:
        assert customer_page in navigation

    for internal_page in [
        "dashboard.html",
        "backtest.html",
        "algo-architecture.html",
        "algo-config.html",
        "verify.html",
        "distributor.html",
        "order-detail.html",
    ]:
        assert internal_page in navigation

    assert "internalMode" in navigation


def test_formal_adapter_does_not_import_demo_data_or_static_business_rows() -> None:
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")

    assert "from './demoData'" not in adapter
    assert "from \"./demoData\"" not in adapter
    assert "createStaticWorkbenchData" not in adapter
    assert "createStaticRuleCluesData" not in adapter

    for required in [
        "getReportContext",
        "getMyManufacturers",
        "getWorkbench",
        "getDailyDetectorStatus",
        "getDailyDetectorClues",
        "getDisplayLookupStatus",
        "getRuntimeProfile",
    ]:
        assert required in adapter or required in read(FRONTEND / "src" / "services" / "backendApi.js")


def test_url_context_parameters_are_preserved_by_adapter() -> None:
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")

    for required in [
        "backendBaseUrl",
        "user_id",
        "observation_date",
        "report_month",
        "run_date",
        "probability_report_month",
        "detector_run_date",
        "manufacturer_code",
        "horizon",
        "top_n",
        "sort_by",
        "demoMode",
    ]:
        assert required in adapter


def test_frontend_default_backend_points_to_project_api_port() -> None:
    backend_api = read(FRONTEND / "src" / "services" / "backendApi.js")
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")

    assert "http://127.0.0.1:18080" in backend_api
    assert "baseUrl || 'http://127.0.0.1:8000'" not in backend_api
    assert "localStorage.getItem('backendBaseUrl')" not in adapter


def test_frontend_observation_date_uses_square_picker_and_draft_apply_boundary() -> None:
    workbench = read(FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue")
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")

    assert "SquareDatePicker" in workbench
    assert 'v-model="draftQuery.observationDate"' in workbench
    assert "appliedQuery" in workbench
    assert "async function submitQuery()" in workbench
    assert 'type="date"' not in workbench
    assert "概率基准月" not in workbench

    assert "if (!items.length && payload?.ready === false) return null" not in adapter
    assert "payload?.ready !== true && payload?.ready !== 'conditional'" in adapter


def test_clue_detail_has_strict_rule_only_data_path() -> None:
    detail = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityDetailView.vue")
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")
    api = read(FRONTEND / "src" / "services" / "backendApi.js")

    assert "detailMode === 'rule-only'" in detail
    assert "loadRuleOnlyClueDetailData" in detail
    assert "getDetectorClueDetail" in adapter
    assert "/api/v1/detectors/clues/${encodeURIComponent(detectorClueId)}" in api
    assert "规则巡检分数不是月度风险概率" in detail
    assert "仅规则命中不会创建 Recurring 风险候选对象" in detail


def test_candidate_clue_detail_retains_horizon_evidence_and_probability_trend() -> None:
    detail = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityDetailView.vue")
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")

    assert "getRiskEntityDetectorEvidence" in adapter
    assert "getRiskEntityProbabilityTrend" in adapter
    assert "selectedHorizonProfile" in detail
    assert "async function selectHorizon" in detail
    assert "profile.probabilityDisplay" in detail
    assert 'aria-label="月度滚动丢失概率趋势"' in detail
    assert "trendPolyline" in detail
    assert "candidateState.value.detectorEvidence" in detail
    assert "SquareDatePicker" not in detail
    assert 'v-model="draftQuery.manufacturerCode"' not in detail


def test_candidate_probability_trend_uses_real_probability_scale_and_model_change_notice() -> None:
    detail = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityDetailView.vue")
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")

    assert "月度滚动丢失概率趋势" in detail
    assert "trendPointY" in detail
    assert "TREND_MODEL_ARTIFACT_CHANGED" in detail
    assert "Math.max(0.05" not in detail
    assert "probabilityTrendWarnings" in adapter


def test_candidate_probability_trend_has_dynamic_axes_and_direction_encoding() -> None:
    detail = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityDetailView.vue")
    styles = read(FRONTEND / "src" / "styles" / "library" / "_modules.scss")

    for required in [
        "trendYAxis",
        "trendXTicks",
        "trendDirection",
        "trendDirectionText",
        "trend-axis-line",
        "trend-axis-label",
        "trend-summary",
    ]:
        assert required in detail or required in styles
    assert "▲" in detail
    assert "▼" in detail
    assert "个百分点" in detail


def test_frontend_rule_clues_exposes_detector_filters() -> None:
    clues_page = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityListView.vue")
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")

    assert "selectedDetectorFamily" in clues_page
    assert "selectedDetectorId" in clues_page
    assert "ruleCategoryOptions" in clues_page
    assert "ruleSubtypeOptions" in clues_page
    assert "getDetectorCatalog" in adapter
    assert "detector_family" in adapter
    assert "detector_id" in adapter


def test_clues_page_is_reserved_for_detector_inspection() -> None:
    app = read(FRONTEND / "src" / "App.vue")
    navigation = read(FRONTEND / "src" / "layout" / "navigation.js")
    clues_page = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityListView.vue")
    boundary = read(FRONTEND / "AGENTS.md")

    assert "tag: '规则巡检结果'" in app
    assert "text: '规则巡检结果'" in navigation
    assert "loadRuleCluesData" in clues_page
    assert "dailyDetectorClues" in clues_page
    assert "selectedDetectorFamily" in clues_page
    assert "selectedDetectorId" in clues_page
    assert "loadCandidateRankingData" not in clues_page
    assert "createEmptyCandidateRankingData" not in clues_page
    assert "reserved exclusively for displaying entities hit by detector rules" in boundary


def test_clues_page_does_not_expose_monthly_candidate_state() -> None:
    clues_page = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityListView.vue")

    for forbidden in [
        "only_monthly_high_risk",
        "isMonthlyHighRiskEntity",
        "monthlyRiskProbability",
        "involvedAmount",
        "filterTabs",
        "next.set('id', clue.riskEntityId)",
    ]:
        assert forbidden not in clues_page
    assert "clue-detail.html?${next.toString()}" in clues_page


def test_clues_page_uses_four_business_categories_with_dependent_subtypes() -> None:
    clues_page = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityListView.vue")
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")

    for label in ["价格异常", "配送异常", "终端变动", "销量波动"]:
        assert label in adapter
    assert "RULE_CATEGORY_DEFINITIONS" in adapter
    assert "selectedRuleCategory" in clues_page
    assert "ruleCategoryOptions" in clues_page
    assert "ruleSubtypeOptions" in clues_page


def test_workbench_and_clues_share_manual_query_context_without_duplicate_date_control() -> None:
    workbench = read(FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue")
    clues_page = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityListView.vue")
    sidebar = read(FRONTEND / "src" / "layout" / "Sidebar.vue")
    topbar = read(FRONTEND / "src" / "layout" / "Topbar.vue")

    for page in [workbench, clues_page]:
        assert "draftQuery" in page
        assert "appliedQuery" in page
        assert "hasSubmittedQuery" in page
        assert "请设置查询条件并点击查询" in page
        assert "async function submitQuery()" in page
        assert "function syncDraftContext()" in page
        assert "watch(draftQuery, syncDraftContext, { deep: true })" in page
        assert "await manufacturerScope.initialize()" in page
        assert "await loadOptions()" in page

    assert "refreshClues" not in clues_page
    assert '<label class="control-field">\n          <span>观察日期</span>\n          <SquareDatePicker' not in clues_page
    assert "查看规则巡检结果" in workbench
    assert "function navigateWithCurrentContext(event, href)" in sidebar
    assert '@click.prevent="navigateWithCurrentContext($event, item.href)"' in sidebar
    assert "function navigateWithCurrentContext(event, href)" in topbar
    assert '@click.prevent="navigateWithCurrentContext($event, \'index.html\')"' in topbar


def test_p175_topbar_owns_the_only_editable_manufacturer_selector() -> None:
    context_path = FRONTEND / "src" / "context" / "manufacturerScope.js"
    assert context_path.exists()

    app = read(FRONTEND / "src" / "App.vue")
    topbar = read(FRONTEND / "src" / "layout" / "Topbar.vue")
    context = read(context_path)
    workbench = read(FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue")
    clues = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityListView.vue")

    assert "provideManufacturerScope" in app
    assert "useManufacturerScope" in topbar
    assert 'aria-label="全局生产企业"' in topbar
    assert 'v-model="selectedManufacturerCode"' in topbar
    assert "manufacturerOptions" in topbar
    assert "正在加载生产企业" in topbar
    assert "暂无可用生产企业" in topbar
    assert "编码 {{ selectedManufacturer.code }}" not in topbar
    assert "loadManufacturerOptions" in context
    assert "window.history.replaceState" in context

    for page in [workbench, clues]:
        assert "useManufacturerScope" in page
        assert '<select v-model="draftQuery.manufacturerCode">' not in page
        assert '<select v-model="query.manufacturerCode">' not in page

    assert "pinia" not in (app + topbar + context).lower()


def test_p175_manufacturer_changes_reload_scoped_pages_with_stale_response_guards() -> None:
    workbench = read(FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue")
    detail = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityDetailView.vue")
    pages = [
        workbench,
        read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityListView.vue"),
        detail,
        read(FRONTEND / "src" / "modules" / "oneshot-monitor" / "OneshotMonitorView.vue"),
    ]

    for page in pages:
        assert "useManufacturerScope" in page
        assert "requestSequence" in page
        assert "sequence !== requestSequence" in page
        assert "watch(manufacturerCode" in page

    assert "manufacturerCode: manufacturerCode.value" in detail
    assert "function cluesHref()" in workbench
    assert "manufacturerCode: manufacturerCode.value" in workbench


def test_p175_business_pages_share_one_shell_and_manufacturer_empty_scope_copy() -> None:
    layout = read(FRONTEND / "src" / "styles" / "library" / "_layout.scss")
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")
    views = [
        read(FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue"),
        read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityListView.vue"),
        read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityDetailView.vue"),
        read(FRONTEND / "src" / "modules" / "oneshot-monitor" / "OneshotMonitorView.vue"),
    ]

    assert ".page-shell" in layout
    assert "max-width: 1280px" in layout
    assert all('class="page-shell' in view for view in views)
    assert "当前生产企业在所选条件下暂无月度候选结果" in adapter
    assert "当前生产企业在所选观察日期暂无规则线索" in adapter
    assert "当前生产企业暂无新进终端记录" in adapter


def test_p201_oneshot_workbench_is_fact_only_and_server_paginated() -> None:
    view = read(FRONTEND / "src" / "modules" / "oneshot-monitor" / "OneshotMonitorView.vue")
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")
    combined = view + adapter

    for required in [
        "新进终端工作台",
        "首次采购日期",
        "首次采购时点金额",
        "距首购天数",
        "page_size",
        "sort_order",
        "ONESHOT_RESULT_NOT_AVAILABLE",
        "status: 'error'",
    ]:
        assert required in combined
    for forbidden in [
        "repurchase_propensity",
        "expected_repurchase_amount",
        "high_repurchase_propensity_count",
        "ranking_basis",
        "复购倾向",
        "预计复购金额",
        "复购促进优先级",
    ]:
        assert forbidden not in combined
    assert "不等于已经流失" in view
    assert "未使用 Recurring 或其他候选数据替代" in adapter


def test_frontend_does_not_depend_on_local_model_or_prototype_paths() -> None:
    scanned_files = [
        *FRONTEND.glob("*.html"),
        *FRONTEND.glob("src/**/*.js"),
        *FRONTEND.glob("src/**/*.vue"),
        *FRONTEND.glob("src/**/*.scss"),
    ]
    combined = "\n".join(read(path) for path in scanned_files)

    for forbidden in ["algo_main", "daily_work/prototype", "risk_model_core", "RiskResultBatch"]:
        assert forbidden not in combined
