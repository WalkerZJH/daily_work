from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "front_end"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_algorithm_architecture_page_exists_with_terminal_loss_chain() -> None:
    page = FRONTEND / "algo-architecture.html"
    assert page.exists()
    text = read(page)

    for term in [
        "终端不丢算法链路",
        "数据预处理与基线",
        "主干风险模型",
        "候选池与",
        "损失价值",
        "新进终端监测",
        "每日规则巡检",
        "探测器证据链",
        "证据融合与状态决策",
        "结构化证据包",
        "回测与验收",
    ]:
        assert term in text


def test_algorithm_architecture_page_keeps_customer_story_not_internal_paths() -> None:
    text = read(FRONTEND / "algo-architecture.html")

    for forbidden in [
        "risk_algorithm_core",
        "risk_model_core",
        "risk_result_batch",
        "project backend",
        "front_end",
        "bounded worklist",
        "asof",
        "artifact",
        "customer-facing probability service",
        "auto_dispatch_allowed",
    ]:
        assert forbidden not in text


def test_algorithm_architecture_page_renders_mathjax_formulas() -> None:
    text = read(FRONTEND / "algo-architecture.html")

    for term in [
        "window.MathJax",
        "\\(",
        "\\[",
        "\\text{ADI}",
        "\\text{CV}^2",
        "\\text{Recall@K}",
        "\\text{Recall}",
        "\\text{Precision}",
    ]:
        assert term in text

    math_panels = re.findall(r'<div class="math-panel">(.*?)</div>', text, flags=re.S)
    assert math_panels
    for formula in math_panels:
        formula = formula.strip()
        assert formula.startswith("\\[")
        assert formula.endswith("\\]")
        assert not formula.startswith("\\\\[")
        assert "\\\\[" not in formula
        assert "\\\\]" not in formula


def test_algorithm_architecture_page_documents_recall_precision_confusion_matrix() -> None:
    text = read(FRONTEND / "algo-architecture.html")
    for term in [
        "补充口径：召回与精度",
        "confusion-matrix",
        "TP",
        "FP",
        "FN",
        "TN",
        "\\text{Recall}=\\frac{TP}{TP+FN}",
        "\\text{Precision}=\\frac{TP}{TP+FP}",
    ]:
        assert term in text


def test_algorithm_architecture_page_documents_oneshot_repurchase_logic() -> None:
    text = read(FRONTEND / "algo-architecture.html")

    for term in [
        "oneshot 复购倾向计算",
        "首次采购后复购倾向",
        "首采金额",
        "首采后天数",
        "复购倾向分层",
        "复购促进优先级",
    ]:
        assert term in text


def test_algorithm_architecture_page_uses_current_metric_labels_without_banned_names() -> None:
    text = read(FRONTEND / "algo-architecture.html")

    for term in [
        "排序能力",
        "稀有事件识别",
        "稀有事件识别提升",
        "校准表现",
        "概率误差",
        "前10%名单召回",
        "命中精度",
    ]:
        assert term in text

    for forbidden in ["AUC", "ECE", "PR-AUC", "Brier", "LogLoss", "XGBoost", "LightGBM", "CatBoost"]:
        assert forbidden not in text


def test_algorithm_architecture_page_is_in_static_navigation_and_vite_inputs() -> None:
    layout_text = read(FRONTEND / "layout" / "layout.js")
    src_nav_text = read(FRONTEND / "src" / "layout" / "navigation.js")
    vite_config = read(FRONTEND / "vite.config.js")

    for text in [layout_text, src_nav_text]:
        assert "algo-architecture.html" in text
        assert "算法链路说明" in text

    assert "algoArchitecture" in vite_config
    assert "algo-architecture.html" in vite_config
