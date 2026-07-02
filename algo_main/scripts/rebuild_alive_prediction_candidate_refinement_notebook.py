#!/usr/bin/env python
"""Rebuild the alive prediction M1-M7 candidate refinement story notebook."""

from __future__ import annotations

import json
from pathlib import Path


def md(cells: list[dict], source: str) -> None:
    cells.append({"cell_type": "markdown", "metadata": {}, "source": source.splitlines(True)})


def code(cells: list[dict], source: str) -> None:
    cells.append(
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": source.splitlines(True),
        }
    )


def build_notebook() -> dict:
    cells: list[dict] = []
    md(
        cells,
        "# Alive Prediction M1-M7 主干算法链路展示\n\n"
        "本 notebook 只读已有 `reports/`，展示从 Stage 1 概率 scorer 到 M7 structured evidence bundle，再到静态线索卡样式原型的完整链路。"
        "它不训练模型、不重新运行 M1-M7、不调参、不读取 parquet、不调用 LLM、不生成正式线索卡。",
    )
    md(
        cells,
        "## 0. 本阶段结论\n\n"
        "在不接入 LLM 的前提下，本阶段已经完成从概率 scorer 到结构化线索材料与静态样式原型的闭环。\n\n"
        "当前链路：\n\n"
        "```text\n"
        "Stage 1 scorer\n"
        "→ M1 business priority candidate pool\n"
        "→ M2 one-shot repeat propensity\n"
        "→ M3 survival-lite\n"
        "→ M4 detector evidence\n"
        "→ M5 candidate status decision\n"
        "→ M7 structured evidence bundle\n"
        "→ static line-card review package\n"
        "```\n\n"
        "这表示当前阶段已结束，不接入 LLM；后续如要进入 LLM/MCP，只能在结构化材料之上做受控表达。",
    )
    md(cells, "## 运行环境与只读报告加载")
    code(
        cells,
        '''from pathlib import Path
import sys

import pandas as pd
from IPython.display import Markdown, display

PROJECT_ROOT = Path.cwd()
if PROJECT_ROOT.name == "notebooks":
    PROJECT_ROOT = PROJECT_ROOT.parent

SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from alg.evaluation.alive_prediction_refinement_story import (
    bool_all_false,
    claim_coverage,
    correction_summary,
    detector_hit_counts,
    extract_static_card_excerpt,
    final_boundary_table,
    load_csv_if_exists,
    m1_summary,
    missing_files_report,
    numeric_summary,
    read_md_head,
    stage_overview,
    value_counts_table,
)

pd.set_option("display.max_columns", 180)
pd.set_option("display.width", 240)

print(f"PROJECT_ROOT={PROJECT_ROOT}")
display(stage_overview(PROJECT_ROOT))
missing = missing_files_report(PROJECT_ROOT)
display(missing[~missing["exists"]])
display(final_boundary_table())''',
    )
    md(
        cells,
        "## 1. 数据与对象语义\n\n"
        "M0/M1-M7 中本阶段固定三类对象：\n\n"
        "- `recurring_business_priority`：recurring 主表候选，来自业务优先级排序。\n"
        "- `one_shot_attention`：one-shot 旁路关注表，后续只解释 repeat probability。\n"
        "- `demand_shape_observation`：需求形态观察旁路表，不能当作主高风险候选。\n\n"
        "必须保持：三类对象不取并集，不统一评分。`business_priority_score_H` 不是概率；"
        "`one-shot repeat_probability_H` 不是 recurring `churn_probability_H`；detector `severity/confidence` 也不是概率。",
    )
    md(cells, "## 2. Stage 1 概率 scorer 回顾")
    code(
        cells,
        '''display(pd.DataFrame([
    {"item": "probability_candidate_v1", "value": "logistic_regression + frequency_decay_v1 + raw"},
    {"item": "business_usable_probability_baseline", "value": "true"},
    {"item": "scope_for_main_decision", "value": "recurring_only"},
]))

cal_v2 = load_csv_if_exists(PROJECT_ROOT / "reports/alive_prediction_calibration_v2/calibration_v2_metrics_by_fold.csv")
decision_v2 = load_csv_if_exists(PROJECT_ROOT / "reports/alive_prediction_calibration_v2/probability_candidate_v1_decision_v2.csv")
display(decision_v2 if decision_v2 is not None else pd.DataFrame([{"warning": "calibration v2 decision missing"}]))
if cal_v2 is not None:
    cols = [c for c in ["model", "feature_set", "calibration_method", "horizon", "brier_score", "log_loss", "ece", "auc", "pr_auc"] if c in cal_v2.columns]
    display(cal_v2[cols].head(30))
else:
    display(pd.DataFrame([{"warning": "calibration v2 metrics missing"}]))

display(Markdown(read_md_head(PROJECT_ROOT / "reports/alive_prediction_calibration_v2/calibration_v2_summary.md", 1800)))''',
    )
    md(cells, "## 3. M1 业务候选池")
    code(
        cells,
        '''m1 = m1_summary(PROJECT_ROOT)
display(m1["counts"])
display(m1["selected_horizons"])
display(m1["primary_horizon"])
display(m1["selection_reason"])
display(m1["audit"])

display(Markdown("""
**口径说明**

- 主表只来自 `relative_business_priority_score_H = churn_probability_H × relative_value_at_risk_H` 排序。
- one-shot / demand-shape observation 未并入 recurring 主表。
- H3/H6/H12 底层仍保留 by-horizon 结果，entity-level 主表只选择 primary_horizon 作为展示入口。
"""))''',
    )
    md(cells, "## 4. Demand-shape observation 膨胀与修正")
    code(
        cells,
        '''corr = correction_summary(PROJECT_ROOT)
display(corr["counts"])
display(corr["history_sufficiency"])
display(Markdown(corr["gate"]))

display(Markdown("""
**解释**

raw demand-shape observation 是审计/观察全集，不是首页候选列表。
后续展示使用 display-ready observation，并通过 latest cutoff、H12、history_sufficiency、manufacturer top-N 等规则压缩。
"""))''',
    )
    md(cells, "## 5. M2 one-shot repeat propensity")
    code(
        cells,
        '''m2_base = PROJECT_ROOT / "reports/alive_prediction_one_shot_repeat_v1"
m2_enriched = load_csv_if_exists(m2_base / "one_shot_attention_candidates_enriched.csv")
m2_metrics = load_csv_if_exists(m2_base / "one_shot_repeat_metrics.csv")
m2_explain = load_csv_if_exists(m2_base / "one_shot_explanation_factors.csv")
m2_prior = load_csv_if_exists(m2_base / "one_shot_group_prior_report.csv")

display(pd.DataFrame([
    {"table": "one_shot_attention_candidates_enriched", "row_count": len(m2_enriched) if m2_enriched is not None else None},
    {"table": "one_shot_explanation_factors", "row_count": len(m2_explain) if m2_explain is not None else None},
    {"table": "one_shot_group_prior_report", "row_count": len(m2_prior) if m2_prior is not None else None},
]))
display(value_counts_table(m2_enriched, "horizon"))
display(value_counts_table(m2_enriched, "selected_attention_policy"))
display(numeric_summary(m2_enriched, [
    "repeat_probability_H",
    "one_shot_non_repeat_risk_H",
    "one_shot_retention_risk_score_H",
    "one_shot_conversion_opportunity_score_H",
    "one_shot_balanced_attention_score_H",
]))
display(m2_metrics if m2_metrics is not None else pd.DataFrame([{"warning": "one-shot metrics missing"}]))
display(Markdown(read_md_head(m2_base / "one_shot_repeat_v1_summary.md", 1800)))

display(Markdown("""
`repeat_probability_H` 表示首次采购后 H 窗口复购概率。它不是 recurring `churn_probability_H`。
"""))''',
    )
    md(cells, "## 6. M3 survival-lite")
    code(
        cells,
        '''m3_base = PROJECT_ROOT / "reports/alive_prediction_survival_lite_v1"
m3 = load_csv_if_exists(m3_base / "survival_refinement_results.csv")
display(pd.DataFrame([{"input_candidate_rows": len(m3) if m3 is not None else None}]))
display(value_counts_table(m3, "history_sufficiency_flag"))
display(value_counts_table(m3, "survival_state"))
display(value_counts_table(m3, "demand_shape_route"))
display(value_counts_table(m3, "expected_interval_source"))
if m3 is not None and "survival_state" in m3.columns:
    overdue = m3["survival_state"].isin(["materially_overdue", "likely_churn_interval"]).sum()
    display(pd.DataFrame([{"materially_or_likely_churn_interval": int(overdue)}]))
display(Markdown(read_md_head(m3_base / "survival_leakage_audit.md", 1800)))

display(Markdown("""
M3 只处理 recurring 主表，不处理 one-shot。
M3 不改变 `churn_probability_H`，也不改变 business priority。
"""))''',
    )
    md(cells, "## 7. M4 detector evidence")
    code(
        cells,
        '''m4_base = PROJECT_ROOT / "reports/alive_prediction_detectors_v1"
det = load_csv_if_exists(m4_base / "detector_evidence_results.csv")
family = load_csv_if_exists(m4_base / "detector_family_summary.csv")
display(pd.DataFrame([{"detector_evidence_rows": len(det) if det is not None else None}]))
display(detector_hit_counts(det))
display(family if family is not None else pd.DataFrame([{"warning": "detector family summary missing"}]))
display(Markdown(read_md_head(m4_base / "detector_semantics_audit.md", 1800)))

display(Markdown("""
detector `severity/confidence` 不是概率。
price/delivery v1 仅 interface-only，不作为有效强证据。
"""))''',
    )
    md(cells, "## 8. M5 candidate status decision")
    code(
        cells,
        '''m5_base = PROJECT_ROOT / "reports/alive_prediction_status_decision_v1"
m5 = load_csv_if_exists(m5_base / "candidate_status_decision.csv")
display(pd.DataFrame([{"candidate_status_decision_rows": len(m5) if m5 is not None else None}]))
display(value_counts_table(m5, "candidate_type"))
display(value_counts_table(m5, "final_candidate_status"))
display(value_counts_table(m5, "review_priority"))
display(value_counts_table(m5, "evidence_strength"))
if m5 is not None:
    display(pd.DataFrame([
        {"metric": "priority_review_count", "value": int(m5["final_candidate_status"].eq("priority_review").sum()) if "final_candidate_status" in m5.columns else None},
        {"metric": "auto_dispatch_allowed_all_false", "value": bool_all_false(m5, "auto_dispatch_allowed")},
    ]))
display(Markdown(read_md_head(m5_base / "status_decision_semantics_audit.md", 1800)))

display(Markdown("""
P0 = 0 / strong = 0 是 v1 保守限制。
当前结果适合作为人工复核材料，不适合自动派单。
"""))''',
    )
    md(cells, "## 9. M7 structured evidence bundle")
    code(
        cells,
        '''m7_base = PROJECT_ROOT / "reports/alive_prediction_evidence_bundle_v1"
bundle = load_csv_if_exists(m7_base / "structured_evidence_bundle.csv")
completeness = load_csv_if_exists(m7_base / "evidence_bundle_completeness_report.csv")
display(pd.DataFrame([{"structured_evidence_bundle_rows": len(bundle) if bundle is not None else None}]))
display(value_counts_table(bundle, "candidate_type"))
display(value_counts_table(bundle, "final_candidate_status"))
display(claim_coverage(bundle, ["allowed_claims", "forbidden_claims", "recommended_action_candidates"]))
display(pd.DataFrame([
    {"metric": "auto_dispatch_allowed_all_false", "value": bool_all_false(bundle, "auto_dispatch_allowed")},
    {"metric": "evidence_timeline_available_all_false", "value": bool_all_false(bundle, "evidence_timeline_available")},
]))
display(completeness if completeness is not None else pd.DataFrame([{"warning": "bundle completeness missing"}]))
display(Markdown(read_md_head(m7_base / "evidence_bundle_next_stage_readiness.md", 1800)))

display(Markdown("""
M7 不是线索卡，不调用 LLM，只生成线索卡原材料。
M6 cache 未实现，仅预留 `evidence_timeline_*` 字段。
"""))''',
    )
    md(cells, "## 10. End-to-end sample review")
    code(
        cells,
        '''review_base = PROJECT_ROOT / "reports/alive_prediction_evidence_bundle_review_v1"
sample = load_csv_if_exists(review_base / "evidence_bundle_stratified_sample.csv")
claim_audit = load_csv_if_exists(review_base / "evidence_bundle_claim_consistency_audit.csv")
action_audit = load_csv_if_exists(review_base / "evidence_bundle_actionability_audit.csv")
display(pd.DataFrame([{"sample_rows": len(sample) if sample is not None else None}]))
display(value_counts_table(sample, "final_candidate_status"))
display(value_counts_table(sample, "candidate_type"))
if claim_audit is not None and "claim_check_pass" in claim_audit.columns:
    claim_pass = claim_audit["claim_check_pass"].fillna(False).astype(str).str.lower().isin(["true", "1", "yes", "y"])
    display(pd.DataFrame([{"claim_consistency_violations": int((~claim_pass).sum())}]))
if action_audit is not None and "actionable_flag" in action_audit.columns:
    action_pass = action_audit["actionable_flag"].fillna(False).astype(str).str.lower().isin(["true", "1", "yes", "y"])
    display(pd.DataFrame([{"actionability_pass_rate": float(action_pass.mean())}]))
display(Markdown(read_md_head(review_base / "evidence_bundle_llm_readiness_report.md", 1800)))''',
    )
    md(cells, "## 11. 静态线索卡样式原型")
    code(
        cells,
        '''static_base = PROJECT_ROOT / "reports/alive_prediction_static_line_card_review_v1"
static_index = load_csv_if_exists(static_base / "static_line_card_sample_index.csv")
field_complete = load_csv_if_exists(static_base / "static_line_card_field_completeness.csv")
claim_boundary = load_csv_if_exists(static_base / "static_line_card_claim_boundary_audit.csv")
display(pd.DataFrame([{"static_card_sample_rows": len(static_index) if static_index is not None else None}]))
display(value_counts_table(static_index, "final_candidate_status"))
display(value_counts_table(static_index, "candidate_type"))
if field_complete is not None and "card_complete" in field_complete.columns:
    complete = field_complete["card_complete"].fillna(False).astype(str).str.lower().isin(["true", "1", "yes", "y"])
    display(pd.DataFrame([{"card_complete_rate": float(complete.mean())}]))
if claim_boundary is not None and "claim_boundary_pass" in claim_boundary.columns:
    boundary = claim_boundary["claim_boundary_pass"].fillna(False).astype(str).str.lower().isin(["true", "1", "yes", "y"])
    display(pd.DataFrame([{"claim_boundary_pass_rate": float(boundary.mean()), "claim_boundary_violations": int((~boundary).sum())}]))
display(Markdown(read_md_head(static_base / "static_line_card_llm_readiness_note.md", 1800)))

display(Markdown("### 静态样例摘录\\n\\n" + extract_static_card_excerpt(PROJECT_ROOT, 5000)))''',
    )
    md(
        cells,
        "## 12. 本阶段边界与未完成事项\n\n"
        "本阶段已完成：\n\n"
        "- M1–M7 链路；\n"
        "- 静态线索卡样式原型；\n"
        "- 人工复核包；\n"
        "- 语义护栏；\n"
        "- allowed / forbidden claims；\n"
        "- no LLM；\n"
        "- no auto dispatch；\n"
        "- M6 interface only。\n\n"
        "本阶段未完成：\n\n"
        "- LLM/MCP 线索卡；\n"
        "- M6 evidence timeline cache；\n"
        "- 客户真实流失样本回测；\n"
        "- VP 每日屏；\n"
        "- 工单闭环；\n"
        "- 干预反馈校准；\n"
        "- 正式上线部署。",
    )
    md(
        cells,
        "## 13. 下一步建议\n\n"
        "1. 先人工复核 20–50 张静态样例；\n"
        "2. 确认需求侧是否接受 one-shot 推荐策略；\n"
        "3. 确认 P0=0 / strong=0 是否过于保守；\n"
        "4. 如暂不接 LLM，可进入日报/VP 每日屏 prototype；\n"
        "5. 如接 LLM，只允许 LLM 改写 `allowed_claims` 和 `recommended_action_candidates`，不得改分数、状态、证据和优先级。",
    )
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python (alg-ml)", "language": "python", "name": "alg-ml"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "notebooks/03_alive_prediction_candidate_refinement_story.ipynb"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_notebook(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
