from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/run_alive_prediction_sanity_reports.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("run_alive_prediction_sanity_reports", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _synthetic_model_base() -> pd.DataFrame:
    base = []
    for idx, date in enumerate(["2023-01-15", "2024-01-15", "2025-01-15"]):
        base.append(
            {
                "row_uid": f"row-{idx}",
                "order_detail_id": f"detail-{idx}",
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_code": "d1",
                "drug_category_code": "cat1",
                "purchase_time": date,
                "raw_sensitive_purchase_quantity": 10 + idx,
                "raw_sensitive_purchase_amount": 100 + idx,
                "raw_sensitive_delivery_quantity": 10 + idx,
                "raw_sensitive_arrival_quantity": 10 + idx,
                "order_phase_code": 60,
                "delivery_state_code": 5,
                "order_failure_flag": 0,
                "order_terminal_flag": 1,
            }
        )
    return pd.DataFrame(base)


def test_cache_hit_does_not_call_builder(tmp_path):
    module = _load_script_module()
    cache_path = tmp_path / "object.parquet"
    stats = {"hit": 0, "miss": 0, "written": 0}
    manifest = {}
    meta = {"source_model_base_path": "x", "source_model_base_mtime": 1, "source_model_base_size": 2}

    first = module._load_or_build_dataframe(
        "object",
        cache_path,
        meta,
        lambda: pd.DataFrame({"value": [1]}),
        True,
        False,
        stats,
        manifest,
    )
    assert first["value"].tolist() == [1]

    def fail_builder():
        raise AssertionError("builder should not be called on cache hit")

    second = module._load_or_build_dataframe(
        "object",
        cache_path,
        meta,
        fail_builder,
        True,
        False,
        stats,
        manifest,
    )
    assert second["value"].tolist() == [1]
    assert stats["hit"] == 1
    assert stats["written"] == 1


def test_refresh_cache_rebuilds_and_overwrites(tmp_path):
    module = _load_script_module()
    cache_path = tmp_path / "object.parquet"
    stats = {"hit": 0, "miss": 0, "written": 0}
    manifest = {}
    meta = {"source_model_base_path": "x", "source_model_base_mtime": 1, "source_model_base_size": 2}

    module._load_or_build_dataframe("object", cache_path, meta, lambda: pd.DataFrame({"value": [1]}), True, False, stats, manifest)
    rebuilt = module._load_or_build_dataframe("object", cache_path, meta, lambda: pd.DataFrame({"value": [2]}), True, True, stats, manifest)
    assert rebuilt["value"].tolist() == [2]
    assert pd.read_parquet(cache_path)["value"].tolist() == [2]


def test_cache_file_names_distinguish_cutoff_and_status_flag():
    module = _load_script_module()
    common = {
        "stem": "alive_prediction_features",
        "drug_group_source": "drug_code",
        "candidate_policy": "monitorable",
        "max_monitor_gap_months": 12,
        "horizons": (3, 6, 12),
    }
    q4_status0 = module._cache_name(**common, start_cutoff="2024-10", end_cutoff="2024-12", include_status_history=False)
    full_status0 = module._cache_name(**common, start_cutoff="2024-01", end_cutoff="2024-12", include_status_history=False)
    q4_status1 = module._cache_name(**common, start_cutoff="2024-10", end_cutoff="2024-12", include_status_history=True)
    assert q4_status0 != full_status0
    assert q4_status0 != q4_status1


def test_sanity_script_writes_timing_summary_and_manifest(tmp_path, monkeypatch):
    module = _load_script_module()
    model_base_path = tmp_path / "model_base.parquet"
    output_dir = tmp_path / "reports"
    cache_dir = tmp_path / "cache"
    _synthetic_model_base().to_parquet(model_base_path, index=False)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_alive_prediction_sanity_reports.py",
            "--model-base",
            str(model_base_path),
            "--output-dir",
            str(output_dir),
            "--cache-dir",
            str(cache_dir),
            "--start-cutoff",
            "2024-01",
            "--end-cutoff",
            "2024-01",
            "--min-rows",
            "1",
            "--cache-intermediate",
        ],
    )
    assert module.main() == 0
    summary = (output_dir / "sanity_run_summary.md").read_text(encoding="utf-8")
    assert "timing_read_model_base" in summary
    assert "timing_write_reports" in summary
    assert "timing_total_runtime" in summary
    manifest = module._read_json(cache_dir / "cache_manifest.json")
    assert manifest["metadata"]["source_model_base_size"] == model_base_path.stat().st_size
    assert manifest["metadata"]["start_cutoff"] == "2024-01"
    assert manifest["metadata"]["horizons"] == [3, 6, 12]


def test_gitignore_covers_sanity_cache_and_reports():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in [
        "data/cache/*",
        "data/04_facts/*",
        "data/05_features/*",
        "reports/alive_prediction*/",
        "*.parquet",
        "*.joblib",
        "*.pkl",
        "*.skops",
        "*.zip",
    ]:
        assert pattern in gitignore
