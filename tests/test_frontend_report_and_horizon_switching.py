from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "front_end"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_past_daily_report_switch_is_prominent_on_report_page() -> None:
    data = read(FRONTEND / "src" / "modules" / "monthly-demo" / "demoData.js")
    report_page = read(FRONTEND / "src" / "modules" / "monthly-report" / "MonthlyReportView.vue")

    for term in [
        "dailyReportOptions",
        "往期日报切换",
        "selectedReportId",
        "activeDailyReport",
        "report-switcher",
        "2026-07-07",
        "2026-07-06",
    ]:
        assert term in data or term in report_page

    assert "日报规则巡检状态" in report_page
    assert "今日规则线索" in report_page
    assert "已附着规则证据" in report_page
    assert "批次模型指标" not in report_page
    assert "模型关键指标" not in report_page


def test_horizon_switch_is_bound_to_riskcard_detail_not_global_pages() -> None:
    data = read(FRONTEND / "src" / "modules" / "monthly-demo" / "demoData.js")
    detail = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityDetailView.vue")
    workbench = read(FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue")
    list_page = read(FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityListView.vue")

    for term in [
        "riskCardHorizonProfiles",
        "riskCardHorizonTabs",
        "selectedHorizon",
        "activeRiskCard",
        "风险窗口切换",
        "horizon-switcher",
        "3月",
        "6月",
        "12月",
    ]:
        assert term in data or term in detail

    assert '@click="selectedHorizon = horizon"' in detail
    assert 'v-for="horizon in riskCardHorizonTabs"' in detail
    assert "selectedHorizon" not in workbench
    assert "horizon-switcher" not in workbench
    assert "selectedHorizon" not in list_page
    assert "horizon-switcher" not in list_page


def test_backtest_page_uses_loss_value_and_month_labels() -> None:
    page = read(FRONTEND / "src" / "modules" / "monthly-report" / "ProofCaseView.vue")
    data = read(FRONTEND / "src" / "modules" / "monthly-demo" / "demoData.js")

    for term in [
        "历史命中复盘",
        "proofCaseHorizonTabs",
        "selectedHorizon",
        "损失价值",
        "3月",
        "6月",
        "12月",
    ]:
        assert term in page or term in data

    assert "业务评分" not in page
    assert "H3" in data
    assert "H6" in data
    assert "H12" in data
