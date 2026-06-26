
from pathlib import Path
import subprocess

import yaml


def test_key_directories_exist():
    root = Path(__file__).resolve().parents[1]
    expected = [
        "configs",
        "data/01_raw",
        "data/03_cleaned",
        "data/05_features",
        "src/alg/data_access",
        "src/alg/schema",
        "src/alg/features",
        "src/alg/tasks/die_prediction",
        "src/alg/models",
        "src/alg/validation",
        "artifacts/promoted_models",
        "reports/model_comparison",
    ]
    for rel in expected:
        assert (root / rel).exists(), rel


def test_key_configs_exist():
    root = Path(__file__).resolve().parents[1]
    for rel in [
        "environment.yml",
        "configs/data_source.yaml",
        "configs/schema_mapping.yaml",
        "configs/validation.yaml",
    ]:
        assert (root / rel).is_file(), rel


def test_data_source_model_base_path_uses_data_layer():
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "configs/data_source.yaml").read_text(encoding="utf-8"))
    parquet = config["sources"]["parquet"]
    assert parquet["model_base_path"] == "data/03_cleaned/bs_agent_dingdan_model_base.parquet"
    assert parquet["cleaned_path"] == "data/03_cleaned/bs_agent_dingdan_model_base.parquet"


def test_algo_main_does_not_track_generated_data_or_model_artifacts():
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "ls-files", "algo_main"],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    forbidden_suffixes = (".parquet", ".csv", ".xlsx", ".joblib", ".pkl", ".skops", ".zip")
    tracked_artifacts = [
        path for path in result.stdout.splitlines() if path.lower().endswith(forbidden_suffixes)
    ]
    assert tracked_artifacts == []
