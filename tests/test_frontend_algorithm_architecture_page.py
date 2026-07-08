from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "front_end"


def test_algorithm_architecture_page_exists_with_terminal_loss_chain():
    page = FRONTEND / "algo-architecture.html"
    assert page.exists()
    text = page.read_text(encoding="utf-8")

    required_terms = [
        "终端不丢算法链路",
        "领先指标",
        "数据预处理与基线",
        "需求形态分类闸门",
        "主干风险模型",
        "候选池与业务排序",
        "新进终端监测",
        "节奏精查",
        "探测器证据链",
        "证据融合与状态决策",
        "结构化证据包",
        "回测与验收",
    ]
    for term in required_terms:
        assert term in text


def test_algorithm_architecture_page_does_not_use_adapter_layer_as_main_story():
    text = (FRONTEND / "algo-architecture.html").read_text(encoding="utf-8")

    forbidden_terms = [
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
    ]
    for term in forbidden_terms:
        assert term not in text


def test_algorithm_architecture_page_renders_latex_formulas():
    text = (FRONTEND / "algo-architecture.html").read_text(encoding="utf-8")

    required_formula_terms = [
        "window.MathJax",
        "\\(",
        "\\[",
        "\\text{ADI}",
        "\\text{CV}^2",
        "\\text{AUC}",
        "\\text{PRAUC}",
        "\\text{ECE}",
        "\\text{PR-AUC Lift}",
        "\\text{Recall@K}",
        "K_{\\text{actual}}",
        "\\text{Brier}",
        "\\text{LogLoss}",
    ]
    for term in required_formula_terms:
        assert term in text

    assert '<div class="formula">' not in text

    math_panels = re.findall(r'<div class="math-panel">(.*?)</div>', text, flags=re.S)
    assert math_panels
    for formula in math_panels:
        formula = formula.strip()
        assert formula.startswith("\\[")
        assert formula.endswith("\\]")
        assert not formula.startswith("\\\\[")
        assert "\\\\[" not in formula
        assert "\\\\]" not in formula


def test_algorithm_architecture_page_has_no_leader_wording():
    text = (FRONTEND / "algo-architecture.html").read_text(encoding="utf-8")

    assert "领导" not in text


def test_algorithm_architecture_page_documents_oneshot_repurchase_logic():
    text = (FRONTEND / "algo-architecture.html").read_text(encoding="utf-8")

    required_terms = [
        "oneshot 复购倾向计算",
        "首次采购后复购倾向",
        "首采金额",
        "首采后天数",
        "复购倾向分层",
        "复购促进优先级",
    ]
    for term in required_terms:
        assert term in text


def test_algorithm_architecture_page_documents_per_user_fill_strategy_in_chinese():
    text = (FRONTEND / "algo-architecture.html").read_text(encoding="utf-8")

    required_policy_terms = [
        "每个用户 20-50 条",
        "不是整体全局只给 20-50 条",
        "优先复核",
        "人工复核",
        "新进终端关注",
        "补充算法候选",
        "高风险 entity、新进终端复购关注、补充算法候选共同进入主工作台",
        "不足 20 条时展示实际数量",
    ]
    for term in required_policy_terms:
        assert term in text


def test_algorithm_architecture_page_documents_model_metrics_and_actual_topk_share():
    text = (FRONTEND / "algo-architecture.html").read_text(encoding="utf-8")

    required_terms = [
        "主干风险概率模型",
        "oneshot 复购倾向模型",
        "detector 证据排序模型",
        "AUC、PRAUC、ECE、Brier 和 TopK recall",
        "TopK recall 的 K 必须使用实际入选占比",
        "selected_count",
        "evaluation_population",
        "union 后的实际占比回填 K",
        "TopK actual 12.8%",
    ]
    for term in required_terms:
        assert term in text


def test_algorithm_architecture_page_is_in_static_navigation():
    layout_text = (FRONTEND / "layout" / "layout.js").read_text(encoding="utf-8")
    src_nav_text = (FRONTEND / "src" / "layout" / "navigation.js").read_text(encoding="utf-8")

    for text in [layout_text, src_nav_text]:
        assert "algo-architecture.html" in text
        assert "算法链路说明" in text


def test_algorithm_architecture_page_is_in_vite_build_inputs():
    vite_config = (FRONTEND / "vite.config.js").read_text(encoding="utf-8")

    assert "algoArchitecture" in vite_config
    assert "algo-architecture.html" in vite_config
