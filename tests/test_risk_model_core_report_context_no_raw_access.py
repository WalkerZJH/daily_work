from __future__ import annotations

from pathlib import Path


def test_report_context_repository_has_no_raw_access_dependencies() -> None:
    source = Path("risk_model_core/repositories.py").read_text(encoding="utf-8")

    forbidden = [
        "risk_algorithm_core.raw_input",
        "fact_purchase_event",
        "entity_cutoff_feature_table",
        "SQL_DATABASE_URL",
        "sqlalchemy.create_engine",
        "import project",
        "import algo_main",
    ]
    for token in forbidden:
        assert token not in source

