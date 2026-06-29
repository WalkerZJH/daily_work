from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

from alg.artifacts.metadata import build_artifact_metadata, write_metadata


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/migrate_alive_prediction_cache.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("migrate_alive_prediction_cache", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _legacy_file(source_dir: Path, artifact: str, start: str = "2024-01", end: str = "2024-12") -> Path:
    return source_dir / f"{artifact}__drug_code__{start}__{end}__monitorable__gap12__H3_6_12__status0.parquet"


def _write_legacy(source_dir: Path, artifact: str, rows: int = 2, start: str = "2024-01", end: str = "2024-12") -> Path:
    path = _legacy_file(source_dir, artifact, start, end)
    source_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({"value": list(range(rows))})
    df.to_parquet(path, index=False)
    write_metadata(path, build_artifact_metadata(artifact_name=artifact, artifact_type="test", df=df))
    return path


def test_migration_default_dry_run_does_not_copy_move_or_delete(tmp_path):
    module = _load_module()
    source_dir = tmp_path / "cache"
    source = _write_legacy(source_dir, "candidate_entities")
    plan = module.build_migration_plan(source_dir, tmp_path / "data", mode="copy")
    executed = module.execute_plan(plan, mode="copy", confirm=False, overwrite=False)
    target = Path(plan.iloc[0]["target_path"])
    assert source.exists()
    assert not target.exists()
    assert executed.iloc[0]["action"] == "copy_planned"


def test_confirm_copy_copies_and_preserves_source(tmp_path):
    module = _load_module()
    source_dir = tmp_path / "cache"
    source = _write_legacy(source_dir, "candidate_entities")
    plan = module.build_migration_plan(source_dir, tmp_path / "data", mode="copy")
    executed = module.execute_plan(plan, mode="copy", confirm=True, overwrite=False)
    target = Path(executed.iloc[0]["target_path"])
    assert source.exists()
    assert target.exists()
    assert executed.iloc[0]["action"] == "copy_done"


def test_confirm_move_moves_selected_file_but_does_not_delete_unmigrated(tmp_path):
    module = _load_module()
    source_dir = tmp_path / "cache"
    source = _write_legacy(source_dir, "candidate_entities")
    unknown = source_dir / "unknown.parquet"
    pd.DataFrame({"x": [1]}).to_parquet(unknown, index=False)
    plan = module.build_migration_plan(source_dir, tmp_path / "data", mode="move")
    executed = module.execute_plan(plan, mode="move", confirm=True, overwrite=False)
    target = Path(executed[executed["action"] == "move_done"].iloc[0]["target_path"])
    assert not source.exists()
    assert target.exists()
    assert unknown.exists()


def test_existing_target_metadata_match_is_not_overwritten(tmp_path):
    module = _load_module()
    source_dir = tmp_path / "cache"
    source = _write_legacy(source_dir, "candidate_entities", rows=2)
    first_plan = module.build_migration_plan(source_dir, tmp_path / "data", mode="copy")
    module.execute_plan(first_plan, mode="copy", confirm=True, overwrite=False)
    target = Path(first_plan.iloc[0]["target_path"])
    mtime = target.stat().st_mtime_ns
    second_plan = module.build_migration_plan(source_dir, tmp_path / "data", mode="copy")
    assert second_plan.iloc[0]["action"] == "already_exists"
    assert target.stat().st_mtime_ns == mtime
    assert source.exists()


def test_existing_target_metadata_mismatch_is_conflict(tmp_path):
    module = _load_module()
    source_dir = tmp_path / "cache"
    _write_legacy(source_dir, "candidate_entities", rows=2)
    target = (
        tmp_path
        / "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/"
        / "cutoff_2024-01_2024-12/candidate_entities.parquet"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"value": [1, 2, 3]}).to_parquet(target, index=False)
    write_metadata(target, {"artifact_name": "candidate_entities", "row_count": 3})
    plan = module.build_migration_plan(source_dir, tmp_path / "data", mode="copy")
    assert plan.iloc[0]["action"] == "skipped_conflict"
    assert plan.iloc[0]["status"] == "conflict"


def test_fact_targets_do_not_include_cutoff_horizon_or_status(tmp_path):
    module = _load_module()
    source_dir = tmp_path / "cache"
    _write_legacy(source_dir, "fact_purchase_event")
    _write_legacy(source_dir, "fact_entity_month")
    plan = module.build_migration_plan(source_dir, tmp_path / "data", mode="copy")
    for target in plan["target_path"]:
        assert "cutoff_" not in str(target)
        assert "H3_6_12" not in str(target)
        assert "status0" not in str(target)


def test_candidate_target_contains_cutoff_range(tmp_path):
    module = _load_module()
    source_dir = tmp_path / "cache"
    _write_legacy(source_dir, "candidate_entities")
    plan = module.build_migration_plan(source_dir, tmp_path / "data", mode="copy")
    assert "cutoff_2024-01_2024-12" in plan.iloc[0]["target_path"]
