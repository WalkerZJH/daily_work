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


def test_frontend_observation_date_uses_date_input_and_no_probability_month_metric() -> None:
    workbench = read(FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue")
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")

    assert 'type="date"' in workbench
    assert 'v-model="query.observationDate"' in workbench
    assert "query.observationDate" in workbench
    assert "概率基准月" not in workbench

    assert "if (!items.length && payload?.ready === false) return null" not in adapter
    assert "payload?.ready !== true && payload?.ready !== 'conditional'" in adapter


def test_frontend_rule_clues_exposes_detector_filters() -> None:
    clues_page = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityListView.vue")
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")

    assert "selectedDetectorFamily" in clues_page
    assert "selectedDetectorId" in clues_page
    assert "detectorFamilyOptions" in clues_page
    assert "detectorIdOptions" in clues_page
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


def test_workbench_and_clues_share_manual_query_context_without_duplicate_date_control() -> None:
    workbench = read(FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue")
    clues_page = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityListView.vue")
    sidebar = read(FRONTEND / "src" / "layout" / "Sidebar.vue")
    topbar = read(FRONTEND / "src" / "layout" / "Topbar.vue")

    for page in [workbench, clues_page]:
        assert "draftQuery" in page
        assert "appliedQuery" in page
        assert "async function submitQuery()" in page
        assert "function syncDraftContext()" in page
        assert "watch(draftQuery, syncDraftContext, { deep: true })" in page
        assert "onMounted(loadOptions)" in page

    assert "refreshClues" not in clues_page
    assert '<label class="control-field">\n          <span>观察日期</span>\n          <SquareDatePicker' not in clues_page
    assert "查看规则巡检结果" in workbench
    assert "function navigateWithCurrentContext(event, href)" in sidebar
    assert '@click.prevent="navigateWithCurrentContext($event, item.href)"' in sidebar
    assert "function navigateWithCurrentContext(event, href)" in topbar
    assert '@click.prevent="navigateWithCurrentContext($event, \'index.html\')"' in topbar


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
