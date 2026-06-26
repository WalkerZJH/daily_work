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
        "## 0. 环境与路径配置",
        "## 1. 基础规模检查",
        "## 2. 唯一标识符检查",
        "## 4. 地区字段清洗",
        "## 6. 数值字段脱敏影响检查",
        "## 8. 医疗机构等级清洗",
        "## 13. 生成 clean 表",
        "## 14. 生成第二轮 clean/model/audit 样本输出",
        "## 15. 生成 Markdown 数据质量报告",
    ]:
        assert section in text
    assert "sql_sample" in text
    assert "sql_full_to_parquet" in text
    assert "parquet" in text
    assert "delivery_rate" in text
    assert "arrival_rate" in text
    assert "price_from_amount_quantity" in text
    assert "do not infer real unit price" in text
    assert "save_v2_outputs(\n    df_raw," in text
    assert "save_v2_outputs(df_clean" not in text


def test_notebook_is_orchestration_only():
    notebook = json.loads((ROOT / "notebooks/01_BS_Agent_DingDan_EDA_and_Cleaning.ipynb").read_text(encoding="utf-8"))
    code_text = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )
    assert "\ndef " not in code_text
    assert "from alg.cleaning.bs_agent_dingdan import" in code_text


def test_bs_agent_dingdan_cleaning_module_imports():
    import alg.cleaning.bs_agent_dingdan as module

    for name in [
        "load_input_dataframe",
        "save_basic_profile",
        "analyze_numeric_desensitization",
        "apply_order_status_lifecycle",
        "build_alias_table_from_raw",
        "build_clean_table",
        "build_clean_model_audit_v2",
        "build_quality_report",
        "save_v2_outputs",
    ]:
        assert hasattr(module, name)


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
