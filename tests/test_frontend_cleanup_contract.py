from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "front_end"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_removed_static_frontend_pages_are_not_built_or_linked() -> None:
    removed_pages = [
        "algo-architecture.html",
        "verify.html",
        "distributor.html",
        "order-detail.html",
    ]
    removed_assets = ["app.js", "styles.css", "layout/layout.js"]

    for relative_path in removed_pages + removed_assets:
        assert not (FRONTEND / relative_path).exists()

    vite_config = read(FRONTEND / "vite.config.js")
    navigation = read(FRONTEND / "src" / "layout" / "navigation.js")
    combined = vite_config + "\n" + navigation

    for forbidden in removed_pages + removed_assets:
        assert forbidden not in combined


def test_current_static_html_entries_mount_vue_app_only() -> None:
    for page in ["index.html", "dashboard.html", "clues.html", "clue-detail.html", "oneshot.html", "backtest.html"]:
        html = read(FRONTEND / page)
        assert '<div id="app"></div>' in html
        assert 'src="/src/main.js"' in html or 'src=\"/src/main.js\"' in html
        assert "app.js" not in html
        assert "styles.css" not in html


def test_empty_frontend_fallback_does_not_fabricate_business_data() -> None:
    demo_data = read(FRONTEND / "src" / "modules" / "monthly-demo" / "demoData.js")
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")
    combined = demo_data + "\n" + adapter

    for forbidden in [
        "A产品线",
        "B产品线",
        "C产品线",
        "D产品线",
        "西南",
        "补齐",
        "回补",
        "高价值待跟进",
        "P(alive)",
        "business_score: 620",
    ]:
        assert forbidden not in combined

    assert "export const riskEntities = []" in demo_data
    assert "export const dailyDetectorClues = []" in demo_data
    assert "export const workbenchDisplayRows = []" in demo_data
    assert "接口未接通" in combined


def test_frontend_adapter_uses_project_api_not_local_files() -> None:
    adapter = read(FRONTEND / "src" / "modules" / "monthly-demo" / "pageDataAdapter.js")

    for required in [
        "loadWorkbenchData",
        "loadRuleCluesData",
        "loadClueDetailData",
        "getWorkbench",
        "getDailyDetectorStatus",
        "getDailyDetectorClues",
    ]:
        assert required in adapter

    for forbidden in ["readFile", "parquet", "algo_main", "daily_work/prototype"]:
        assert forbidden not in adapter
