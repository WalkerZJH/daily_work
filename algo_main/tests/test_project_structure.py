
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
        "configs/features/alive_prediction_feature_view.yaml",
        "configs/metrics/alive_prediction_metrics.yaml",
        "configs/schema_mapping.yaml",
        "configs/validation.yaml",
    ]:
        assert (root / rel).is_file(), rel


def test_alive_prediction_design_deliverables_exist_and_record_core_decisions():
    root = Path(__file__).resolve().parents[1]
    expected_docs = [
        "docs/algo/alive_prediction_problem_definition.md",
        "docs/algo/entity_grain_research.md",
        "docs/algo/label_definition.md",
        "docs/algo/metric_design.md",
        "docs/algo/data_leakage_guardrails.md",
        "docs/algo/experiment_plan.md",
    ]
    for rel in expected_docs:
        assert (root / rel).is_file(), rel

    combined = "\n".join((root / rel).read_text(encoding="utf-8") for rel in expected_docs)
    for phrase in [
        "全局概率模型",
        "churn_probability_H",
        "value_at_risk",
        "business_priority_score",
        "manufacturer_code × hospital_code × drug_code",
        "H = 3 个月",
        "H = 6 个月",
        "H = 12 个月",
        "rolling-origin temporal split",
        "purged split",
        "概率模型 metrics",
        "业务排序 metrics",
        "BG/NBD",
        "Pareto/NBD",
    ]:
        assert phrase in combined


def test_alive_prediction_configs_record_leakage_and_metric_contracts():
    root = Path(__file__).resolve().parents[1]
    feature_view = yaml.safe_load((root / "configs/features/alive_prediction_feature_view.yaml").read_text(encoding="utf-8"))
    metrics = yaml.safe_load((root / "configs/metrics/alive_prediction_metrics.yaml").read_text(encoding="utf-8"))

    assert feature_view["input"]["model_base"] == "data/03_cleaned/bs_agent_dingdan_model_base.parquet"
    assert feature_view["entity"]["grain"] == ["manufacturer_code", "hospital_code", "drug_group"]
    assert feature_view["entity"]["primary_drug_group_source"] == "drug_code"
    assert feature_view["targets"]["horizons_months"] == [3, 6, 12]
    assert "label_die_H3" in feature_view["excluded_columns"]["future_or_label_like"]
    assert any("business_priority_score" in rule for rule in feature_view["leakage_rules"])

    assert metrics["horizons_months"] == [3, 6, 12]
    assert metrics["validation"]["strategy"] == "rolling_origin_temporal_split"
    assert metrics["validation"]["purged_by_horizon"] is True
    assert "brier_score" in metrics["probability_quality_metrics"]["calibration"]
    assert "captured_value_at_k" in metrics["business_ranking_metrics"]["metrics"]


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
