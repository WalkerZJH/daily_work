from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from alg.cache.cleanup import assert_cleanup_allowed, clean_cache


ROOT = Path(__file__).resolve().parents[1]
MATERIALIZE_PATH = ROOT / "scripts/materialize_alive_prediction_artifacts.py"


def _load_materialize():
    spec = importlib.util.spec_from_file_location("materialize_alive_prediction_artifacts", MATERIALIZE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_clean_cache_default_dry_run_does_not_delete(tmp_path):
    cache_root = tmp_path / "data/cache/alive_prediction/tmp"
    cache_root.mkdir(parents=True)
    file_path = cache_root / "object.parquet"
    file_path.write_text("x", encoding="utf-8")
    candidates = clean_cache(cache_root, dry_run=True, confirm=False)
    assert len(candidates) == 1
    assert file_path.exists()


def test_cleanup_refuses_protected_data_layers(tmp_path):
    protected = tmp_path / "data/04_facts/alive_prediction/object.parquet"
    protected.parent.mkdir(parents=True)
    protected.write_text("x", encoding="utf-8")
    with pytest.raises(PermissionError):
        assert_cleanup_allowed(protected, tmp_path / "data/cache/alive_prediction/tmp")


def test_alive_prediction_scripts_do_not_directly_delete_data_artifacts():
    checked = [
        ROOT / "scripts/run_alive_prediction_sanity_reports.py",
        ROOT / "scripts/run_alive_prediction_small_model_experiments.py",
        ROOT / "scripts/materialize_alive_prediction_artifacts.py",
        ROOT / "scripts/migrate_alive_prediction_cache.py",
    ]
    forbidden = ["unlink(", "os.remove", "shutil.rmtree", "rm -rf", "del /s"]
    for path in checked:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text


def test_materialize_reuses_existing_artifact_without_rebuild(tmp_path):
    module = _load_materialize()
    target = tmp_path / "data/04_facts/alive_prediction/fact_purchase_event__drug_code.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"value": [1]}).to_parquet(target, index=False)
    from alg.artifacts.metadata import write_metadata

    write_metadata(target, {"artifact_name": "fact_purchase_event", "row_count": 1})
    assert module.artifact_exists(target)


def test_materialize_finds_legacy_cache_before_rebuild(tmp_path, monkeypatch):
    module = _load_materialize()
    target = tmp_path / "data/04_facts/alive_prediction/fact_purchase_event__drug_code.parquet"
    monkeypatch.setattr(module, "project_root", lambda: tmp_path)
    source_dir = tmp_path / "data/cache/alive_prediction_sanity"
    source_dir.mkdir(parents=True)
    source = source_dir / "fact_purchase_event__drug_code__2024-01__2024-12__monitorable__gap12__H3_6_12__status0.parquet"
    df = pd.DataFrame({"value": [1]})
    df.to_parquet(source, index=False)
    from alg.artifacts.metadata import build_artifact_metadata, write_metadata

    write_metadata(source, build_artifact_metadata(artifact_name="fact_purchase_event", artifact_type="facts", df=df))
    status = module._maybe_migrate_from_legacy(target, dry_run=True, overwrite=False)
    assert status == "legacy_copy_planned"


def test_no_prediction_script_reads_label_artifacts():
    prediction_scripts = [
        path
        for path in (ROOT / "scripts").glob("*prediction*.py")
        if path.name.startswith("score_") or path.name.startswith("predict_")
    ]
    for path in prediction_scripts:
        if path.name in {
            "run_alive_prediction_sanity_reports.py",
            "run_alive_prediction_small_model_experiments.py",
            "run_alive_prediction_rule_baseline.py",
            "materialize_alive_prediction_artifacts.py",
        }:
            continue
        text = path.read_text(encoding="utf-8")
        assert "alive_labels" not in text
        assert "label_distribution" not in text
