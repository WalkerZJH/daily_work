from __future__ import annotations

from pathlib import Path


def test_frontend_report_context_uses_observation_date_over_stale_month_params() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source = (repo_root / "front_end/src/modules/monthly-demo/pageDataAdapter.js").read_text(encoding="utf-8")

    assert "export function queryToReportContextParams(query)" in source
    assert "getReportContext(queryToReportContextParams(normalized))" in source
    assert "getReportContext(queryToReportContextParams(normalizedQuery))" in source
    assert "if (query.observationDate) return params" in source
    assert "observation_date: query.observationDate" in source
    assert "report_month: query.probabilityReportMonth || query.reportMonth" in source
