from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "front_end"


def read_frontend_file(name: str) -> str:
    return (FRONTEND / name).read_text(encoding="utf-8")


def test_static_navigation_matches_monthly_worklist_positioning():
    for path in [FRONTEND / "layout" / "layout.js", FRONTEND / "src" / "layout" / "navigation.js"]:
        text = path.read_text(encoding="utf-8")
        assert "月报工作台" in text
        assert "风险实体清单" in text
        assert "月报与案例" in text
        assert "算法链路说明" in text
        assert "VP 今日工作台" not in text
        assert "全部风险线索" not in text


def test_vue_canonical_app_routes_monthly_demo_pages():
    text = (FRONTEND / "src" / "App.vue").read_text(encoding="utf-8")

    required_terms = [
        "MonthlyWorkbenchView",
        "RiskEntityListView",
        "RiskEntityDetailView",
        "MonthlyReportView",
        "ProofCaseView",
        "OneshotMonitorView",
    ]
    for term in required_terms:
        assert term in text


def test_vue_homepage_uses_monthly_report_worklist_contract_language():
    text = (FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue").read_text(encoding="utf-8")

    required_terms = [
        "月报工作清单",
        "report_month",
        "score_as_of_date",
        "H6 主视角",
        "RiskEntity",
        "RiskCard",
        "建议动作",
        "高价值终端",
        "模型关键指标",
        "PRAUC",
        "TopK 使用实际入选占比",
    ]
    for term in required_terms:
        assert term in text

    assert "今日新增" not in text


def test_vue_monthly_report_surfaces_batch_context():
    text = (FRONTEND / "src" / "modules" / "monthly-report" / "MonthlyReportView.vue").read_text(encoding="utf-8")

    required_terms = [
        "MonthlyReport",
        "score_batch_id",
        "data_watermark_at",
        "RiskResultBatch",
        "高风险实体",
        "生产商",
        "批次模型指标",
        "TopK recall",
    ]
    for term in required_terms:
        assert term in text


def test_vue_worklist_pages_separate_entities_cards_and_fill_candidates():
    clues = (FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityListView.vue").read_text(encoding="utf-8")
    detail = (FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityDetailView.vue").read_text(encoding="utf-8")
    workbench = (FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue").read_text(encoding="utf-8")
    backtest = (FRONTEND / "src" / "modules" / "monthly-report" / "ProofCaseView.vue").read_text(encoding="utf-8")

    for term in ["RiskEntity", "RiskCard", "证据链", "人工复核"]:
        assert term in clues
    for term in ["RiskCard", "RiskEvidence", "业务可见证据", "建议动作"]:
        assert term in detail
    for term in ["workbenchDisplayRows", "医院 × 药品", "填充到 20 个", "补充算法"]:
        assert term in workbench
    for term in ["Proof-case", "历史命中案例", "成功案例", "产品效果"]:
        assert term in backtest


def test_static_pages_are_vue_mount_shells_for_duplicate_demo_pages():
    for page in ["index.html", "dashboard.html", "clues.html", "clue-detail.html", "oneshot.html", "backtest.html"]:
        text = read_frontend_file(page)
        assert '<div id="app"></div>' in text
        assert 'src="/src/main.js"' in text or "src=\"/src/main.js\"" in text
        assert "app.js" not in text


def test_watchlist_page_is_removed_and_workbench_fills_main_view_to_20():
    assert not (FRONTEND / "watchlist.html").exists()
    assert not (FRONTEND / "src" / "modules" / "risk-worklist" / "ObservationWatchlistView.vue").exists()

    files = [
        FRONTEND / "src" / "App.vue",
        FRONTEND / "src" / "layout" / "navigation.js",
        FRONTEND / "layout" / "layout.js",
        FRONTEND / "vite.config.js",
    ]
    offenders = []
    for file in files:
        text = file.read_text(encoding="utf-8")
        for term in ["watchlist.html", "ObservationWatchlistView", "观察对象", "观察名单"]:
            if term in text:
                offenders.append(f"{file.relative_to(FRONTEND).as_posix()}::{term}")

    assert offenders == []

    data = (FRONTEND / "src" / "modules" / "monthly-demo" / "demoData.js").read_text(encoding="utf-8")
    workbench = (FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue").read_text(encoding="utf-8")
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


def test_user_visible_copy_removes_cautious_and_stage_language():
    visible_files = [
        FRONTEND / "src" / "App.vue",
        FRONTEND / "src" / "layout" / "navigation.js",
        FRONTEND / "layout" / "layout.js",
        FRONTEND / "src" / "modules" / "monthly-demo" / "demoData.js",
        FRONTEND / "src" / "modules" / "monthly-workbench" / "MonthlyWorkbenchView.vue",
        FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityListView.vue",
        FRONTEND / "src" / "modules" / "risk-worklist" / "RiskEntityDetailView.vue",
        FRONTEND / "src" / "modules" / "oneshot-monitor" / "OneshotMonitorView.vue",
        FRONTEND / "src" / "modules" / "monthly-report" / "MonthlyReportView.vue",
        FRONTEND / "src" / "modules" / "monthly-report" / "ProofCaseView.vue",
    ]
    banned_terms = [
        "仅供",
        "不代表",
        "不能作为",
        "不作为",
        "不等同",
        "不替代",
        "不展示",
        "模型训练参数",
        "特征消融",
        "raw SHAP",
        "AUC/ECE",
        "未实现",
        "未展示",
        "未接入",
        "未经过",
        "概率展示受控",
        "不自动派单",
        "默认人工复核",
        "auto_dispatch_allowed=false",
        "不得标成高风险",
    ]

    offenders = []
    for file in visible_files:
        text = file.read_text(encoding="utf-8")
        for term in banned_terms:
            if term in text:
                offenders.append(f"{file.relative_to(FRONTEND).as_posix()}::{term}")

    assert offenders == []


def test_internal_algorithm_debug_pages_are_removed_from_user_frontend():
    assert not (FRONTEND / "algo-config.html").exists()
    assert not (FRONTEND / "algo-health.html").exists()
    assert not (FRONTEND / "src" / "modules" / "algo-config").exists()
    assert not (FRONTEND / "src" / "modules" / "algo-health").exists()

    files = [
        FRONTEND / "src" / "App.vue",
        FRONTEND / "src" / "layout" / "navigation.js",
        FRONTEND / "layout" / "layout.js",
        FRONTEND / "vite.config.js",
    ]
    banned_terms = ["algo-config", "algo-health", "AlgoConfig", "AlgoHealth", "算法配置管理", "接口诊断", "算法日报探查页"]
    offenders = []
    for file in files:
        text = file.read_text(encoding="utf-8")
        for term in banned_terms:
            if term in text:
                offenders.append(f"{file.relative_to(FRONTEND).as_posix()}::{term}")

    assert offenders == []
