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


def test_clues_uses_accessible_detector_cards_with_explicit_query_events() -> None:
    source = (ROOT / "front_end/src/modules/risk-worklist/DetectorCardFilterPanel.vue").read_text(encoding="utf-8")
    assert "aria-expanded" in source
    assert "queryFamily" in source
    assert "queryDetector" in source
    assert "prefers-reduced-motion" in source
    assert "@click=\"toggleFamily(family.id)\"" in source


def test_clue_link_passes_full_entity_key_and_detail_keeps_clue_only_compatibility() -> None:
    list_source = (ROOT / "front_end/src/modules/risk-worklist/RiskEntityListView.vue").read_text(encoding="utf-8")
    detail_source = (ROOT / "front_end/src/modules/risk-worklist/RiskEntityDetailView.vue").read_text(encoding="utf-8")
    adapter_source = (ROOT / "front_end/src/modules/monthly-demo/pageDataAdapter.js").read_text(encoding="utf-8")
    for field in ["manufacturerCode", "hospitalCode", "drugCode", "observationDate"]:
        assert field in list_source
    assert "hasDetectorEntityKey" in detail_source
    assert "hasDetectorEntityKey || clueId ? 'entity-detector'" in detail_source
    assert "getDetectorEntityDetail" in adapter_source
    assert "getDetectorClueDetail(clueId" in adapter_source
    assert "clue.drug_code || clue.evaluation?.drug_code" in adapter_source


def test_release_b_copy_and_entity_evidence_rendering_contract() -> None:
    list_source = (ROOT / "front_end/src/modules/risk-worklist/RiskEntityListView.vue").read_text(encoding="utf-8")
    detail_source = (ROOT / "front_end/src/modules/risk-worklist/RiskEntityDetailView.vue").read_text(encoding="utf-8")
    for copy in ["当日规则命中记录", "当前筛选结果", "同一医院—药品可能命中多条规则", "名称：--"]:
        assert copy in list_source
    for copy in ["当前 Detector 汇总", "计算说明", "涉及金额", "未纳入当前月度概率预测集"]:
        assert copy in detail_source
    assert "v-for=\"hit in detectorEntityHits\"" in detail_source
    assert "probabilityTrend.length" in detail_source
    assert "resetFilters" in list_source
    assert "pagination.totalPages" in list_source
