from __future__ import annotations

from pathlib import Path


def test_project_detector_result_path_does_not_import_algorithm_or_raw_sources() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sources = [
        project_root / "app" / "api" / "routes_detector_results.py",
        project_root / "app" / "services" / "detector_result_service.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in sources)

    for forbidden in [
        "risk_algorithm_core",
        "algo_main",
        "DATABASE_URL",
        "sql_table_adapter",
        "backbone_service",
        "app.detectors",
        "read_csv",
        "read_parquet",
    ]:
        assert forbidden not in text
