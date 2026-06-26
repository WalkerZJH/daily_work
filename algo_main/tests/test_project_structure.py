
from pathlib import Path


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
