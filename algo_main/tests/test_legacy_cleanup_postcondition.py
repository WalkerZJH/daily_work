from __future__ import annotations

from pathlib import Path


def test_entity_complete_v1_is_retained_after_legacy_cleanup() -> None:
    root = Path(__file__).resolve().parents[1]

    assert (root / "data/entity_complete_v1").exists()
    assert (root / "reports/entity_complete_v1").exists()
    assert (root / "reports/entity_complete_v1/07_algorithm_consolidation").exists()


def test_legacy_alive_prediction_report_globs_are_removed() -> None:
    root = Path(__file__).resolve().parents[1]

    legacy_reports = list((root / "reports").glob("alive_prediction_*"))

    assert legacy_reports == []


def test_legacy_alive_prediction_data_paths_are_removed() -> None:
    root = Path(__file__).resolve().parents[1]

    assert not (root / "data/04_facts/alive_prediction").exists()
    assert not (root / "data/05_features/alive_prediction").exists()
    assert not (root / "data/07_outputs/alive_prediction").exists()
