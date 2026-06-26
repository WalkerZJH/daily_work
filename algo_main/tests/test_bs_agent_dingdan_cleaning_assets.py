import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_cleaning_asset_files_exist():
    expected = [
        "notebooks/01_BS_Agent_DingDan_EDA_and_Cleaning.ipynb",
        "docs/data_dictionary/BS_Agent_DingDan字段说明.md",
        "configs/data_schema/bs_agent_dingdan_schema.yaml",
        "configs/mappings/order_status_map.yaml",
        "configs/mappings/order_status_lifecycle_map.yaml",
        "configs/mappings/hospital_grade_map.yaml",
        "configs/mappings/drug_category_map.yaml",
        "configs/mappings/ownership_map.yaml",
        "exports/eda/.gitkeep",
        "exports/clean/.gitkeep",
        "exports/mappings/.gitkeep",
        "exports/raw/.gitkeep",
    ]
    for rel in expected:
        assert (ROOT / rel).exists(), rel


def test_schema_records_desensitization_policy():
    schema = yaml.safe_load((ROOT / "configs/data_schema/bs_agent_dingdan_schema.yaml").read_text(encoding="utf-8"))
    policy = schema["desensitization_policy"]
    assert policy["quantity_fields_share_multiplier"] == "q"
    assert policy["amount_fields_share_multiplier"] == "m"
    assert "infer_real_unit_price_from_amount_divided_by_quantity" in policy["forbidden_analyses"]
    assert "validate_purchase_price_against_purchase_amount_divided_by_purchase_quantity" in policy["forbidden_analyses"]


def test_schema_marks_quantity_and_amount_fields_bounded_usable():
    schema = yaml.safe_load((ROOT / "configs/data_schema/bs_agent_dingdan_schema.yaml").read_text(encoding="utf-8"))
    columns = {c["alias"]: c for c in schema["columns"]}
    for alias in [
        "raw_sensitive_purchase_quantity",
        "raw_sensitive_delivery_quantity",
        "raw_sensitive_arrival_quantity",
        "return_quantity",
    ]:
        assert columns[alias]["algorithm_usable"] is True
        assert columns[alias]["usable_scope"] == "bounded_quantity_ratio_and_trend"
    for alias in [
        "raw_sensitive_purchase_amount",
        "raw_sensitive_delivery_amount",
        "raw_sensitive_arrival_amount",
    ]:
        assert columns[alias]["algorithm_usable"] is True
        assert columns[alias]["usable_scope"] == "bounded_amount_relative_relationship_and_trend"
    assert columns["raw_sensitive_purchase_price"]["algorithm_usable"] is False
    assert columns["void_quantity"]["algorithm_usable"] is False


def test_hospital_level_policy_uses_level_not_detail():
    schema = yaml.safe_load((ROOT / "configs/data_schema/bs_agent_dingdan_schema.yaml").read_text(encoding="utf-8"))
    columns = {c["alias"]: c for c in schema["columns"]}
    assert columns["hospital_level_raw"]["include_in_clean"] is True
    assert columns["hospital_level_raw"]["semantic_type"] == "ordinal_category"
    assert columns["hospital_level_detail_raw"]["include_in_clean"] is False
    assert columns["hospital_level_detail_raw"]["algorithm_usable"] is False


def test_notebook_contains_required_sections_and_modes():
    notebook = json.loads((ROOT / "notebooks/01_BS_Agent_DingDan_EDA_and_Cleaning.ipynb").read_text(encoding="utf-8"))
    text = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    for section in [
        "## 1. 环境与路径配置",
        "## 2. 运行 pipeline",
        "## 3. 展示三张核心表",
        "## 4. model_base 字段检查",
        "## 5. 主键检查",
        "## 6. 订单状态映射检查",
        "## 7. 药品编码与地区检查",
        "## 8. 数值脱敏与矛盾检查",
        "## 9. 质量报告展示",
        "## 10. 汇报结论",
    ]:
        assert section in text
    assert "sample_mode = True" in text
    assert 'output_format = "parquet"' in text
    assert "delivery_rate" in text
    assert "arrival_rate" in text
    assert "run_bs_agent_dingdan_cleaning_pipeline" in text


def test_notebook_is_orchestration_only():
    notebook = json.loads((ROOT / "notebooks/01_BS_Agent_DingDan_EDA_and_Cleaning.ipynb").read_text(encoding="utf-8"))
    code_text = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )
    assert "\ndef " not in code_text
    assert "from alg.cleaning.bs_agent_dingdan_pipeline import run_bs_agent_dingdan_cleaning_pipeline" in code_text
    assert "from alg.cleaning.bs_agent_dingdan import load_env" in code_text


def test_notebook_uses_only_pipeline_as_cleaning_entrypoint():
    notebook = json.loads((ROOT / "notebooks/01_BS_Agent_DingDan_EDA_and_Cleaning.ipynb").read_text(encoding="utf-8"))
    code_text = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )
    forbidden_calls = [
        "save_v2_outputs",
        "save_clean_outputs",
        "build_clean_table",
        "build_clean_model_audit_v2",
        "analyze_numeric_desensitization",
        "build_quality_report",
    ]
    for name in forbidden_calls:
        assert name not in code_text


def test_bs_agent_dingdan_cleaning_module_imports():
    import alg.cleaning.bs_agent_dingdan as module
    from alg.cleaning.bs_agent_dingdan_pipeline import run_bs_agent_dingdan_cleaning_pipeline

    for name in [
        "load_env",
        "apply_order_status_lifecycle",
        "build_alias_table_from_raw",
        "map_status_lifecycle_value",
        "order_status_lifecycle_map_dataframe",
    ]:
        assert hasattr(module, name)
    assert callable(run_bs_agent_dingdan_cleaning_pipeline)


def test_schema_records_second_round_model_columns():
    schema = yaml.safe_load((ROOT / "configs/data_schema/bs_agent_dingdan_schema.yaml").read_text(encoding="utf-8"))
    columns = {c["alias"]: c for c in schema["columns"]}
    assert columns["enterprise_code"]["notes"] == "invalid_by_business_peer_usage"
    assert columns["insurance_drug_code"]["audit_only"] is True
    assert columns["product_name"]["algorithm_usable"] is False
    assert columns["drug_category_raw"]["algorithm_usable"] is False
    assert "order_phase_code" in schema["model_columns"]
    assert "delivery_state_code" in schema["model_columns"]
    assert "hospital_name" not in schema["model_columns"]
    assert "order_status_raw" not in schema["model_columns"]
