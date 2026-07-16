from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_clues_uses_transient_draft_and_applied_request_filters() -> None:
    source = (ROOT / "front_end/src/modules/risk-worklist/RiskEntityListView.vue").read_text(encoding="utf-8")
    assert "draftFilters" in source
    assert "appliedFilters" in source
    assert "loadRuleCluesData" in source
    assert "loadCandidateRankingData" not in source
    assert "watch(draftQuery" not in source
    assert "submitQuery(1)" in source


def test_clue_detail_exposes_rule_evaluation_without_candidate_fields_in_rule_only_section() -> None:
    source = (ROOT / "front_end/src/modules/risk-worklist/RiskEntityDetailView.vue").read_text(encoding="utf-8")
    assert "规则判定值" in source
    assert "ruleClue.currentValue" in source
    assert "ruleClue.baselineValue" in source
    assert "ruleClue.thresholdValue" in source
    assert "管理员配置 ID" in source


def test_adapter_forwards_filters_pagination_and_sorting_as_request_params() -> None:
    source = (ROOT / "front_end/src/modules/monthly-demo/pageDataAdapter.js").read_text(encoding="utf-8")
    for parameter in ["detector_category", "detector_level", "page_size", "sort_order"]:
        assert parameter in source
