from __future__ import annotations

from datetime import date

from app.adapters.sql_table_adapter import SQLTableSourceAdapter


def test_sql_adapter_builds_projected_columns_and_filters_without_select_star() -> None:
    adapter = SQLTableSourceAdapter(
        as_of_date=date(2026, 6, 1),
        enterprise_code="ENT-1",
        province="江苏省",
        row_limit=10,
    )

    spec = adapter.build_query_spec(available_columns={"采购时间", "药品编码", "企业编码", "省"})

    assert spec.selected_columns == ["省", "采购时间", "药品编码", "企业编码"]
    assert "*" not in spec.selected_columns
    assert spec.filters["采购时间"] == date(2026, 6, 1)
    assert spec.filters["企业编码"] == "ENT-1"
    assert spec.filters["省"] == "江苏省"
    assert spec.row_limit == 10
