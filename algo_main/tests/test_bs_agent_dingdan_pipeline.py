from pathlib import Path

import pandas as pd

from alg.cleaning.bs_agent_dingdan import (
    map_status_lifecycle_value,
    order_status_lifecycle_map_dataframe,
)
from alg.cleaning.bs_agent_dingdan_pipeline import run_bs_agent_dingdan_cleaning_pipeline


ROOT = Path(__file__).resolve().parents[1]


def _raw_sample() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "数据唯一标识符": "row-1",
                "订单明细ID": "detail-1",
                "省编码": "340000",
                "市编码": "340300",
                "县区编码": "340323",
                "采购时间": "2026-01-01",
                "药品编码": "drug-a",
                "药品医保编码": "drug-a",
                "通用名": "药品A",
                "商品名": "商品A",
                "采购价(元)": 10,
                "采购数量": 100,
                "采购金额(元)": 1000,
                "配送数量": 100,
                "配送金额(元)": 1000,
                "到货数量": 100,
                "到货金额(元)": 1000,
                "订单状态": "配送完成",
                "企业编码": "ent-a",
                "医疗机构等级": "三级",
                "医疗机构详细等级": "三级甲等",
                "医疗机构编码": "hosp-a",
                "医疗机构": "医院A",
                "配送企业编码": "dist-a",
                "配送企业": "配送A",
                "生产企业编码": "maker-a",
                "生产企业": "生产A",
                "药品类别": "类别A",
                "所有制形式": "公立",
                "退回数量": 0,
            },
            {
                "数据唯一标识符": "row-2",
                "订单明细ID": "detail-2",
                "省编码": "340000",
                "市编码": "340300",
                "县区编码": "340323",
                "采购时间": "2026-01-02",
                "药品编码": "drug-a",
                "药品医保编码": "drug-b",
                "通用名": "药品A",
                "商品名": "",
                "采购价(元)": 10,
                "采购数量": 100,
                "采购金额(元)": 1000,
                "配送数量": 0,
                "配送金额(元)": 0,
                "到货数量": 0,
                "到货金额(元)": 0,
                "订单状态": "已下发网采证明",
                "企业编码": "ent-b",
                "医疗机构等级": "二级",
                "医疗机构详细等级": "二级乙等",
                "医疗机构编码": "hosp-b",
                "医疗机构": "医院B",
                "配送企业编码": "dist-b",
                "配送企业": "配送B",
                "生产企业编码": "maker-b",
                "生产企业": "生产B",
                "药品类别": "类别B",
                "所有制形式": "民营",
                "退回数量": 0,
            },
        ]
    )


def _write_raw(tmp_path: Path) -> Path:
    raw_path = tmp_path / "raw.parquet"
    _raw_sample().to_parquet(raw_path, index=False)
    return raw_path


def test_pipeline_function_importable():
    assert callable(run_bs_agent_dingdan_cleaning_pipeline)


def test_pipeline_default_writes_model_and_report_only(tmp_path):
    raw_path = _write_raw(tmp_path)
    result = run_bs_agent_dingdan_cleaning_pipeline(
        raw_cache_path=raw_path,
        output_dir=tmp_path / "exports",
    )
    paths = result["output_paths"]
    assert Path(paths["model_base"]["parquet"]).exists()
    assert Path(paths["quality_report"]).exists()
    assert "clean_sample_v2" not in paths
    assert "audit_sample" not in paths


def test_pipeline_optional_clean_and_audit_outputs(tmp_path):
    raw_path = _write_raw(tmp_path)
    result = run_bs_agent_dingdan_cleaning_pipeline(
        raw_cache_path=raw_path,
        output_dir=tmp_path / "exports",
        generate_clean=True,
        generate_audit=True,
    )
    assert Path(result["output_paths"]["clean_sample_v2"]).exists()
    assert Path(result["output_paths"]["audit_sample"]).exists()


def test_pipeline_model_and_audit_columns(tmp_path):
    raw_path = _write_raw(tmp_path)
    result = run_bs_agent_dingdan_cleaning_pipeline(
        raw_cache_path=raw_path,
        output_dir=tmp_path / "exports",
        generate_audit=True,
    )
    model = pd.read_parquet(result["output_paths"]["model_base"]["parquet"])
    forbidden = {
        "hospital_name",
        "distributor_name",
        "manufacturer_name",
        "product_name",
        "order_status_raw",
        "hospital_level_raw",
        "hospital_level_label",
        "ownership_type_raw",
        "drug_category_raw",
    }
    assert not forbidden.intersection(model.columns)
    audit = pd.read_csv(result["output_paths"]["audit_sample"])
    for column in [
        "raw_city_code",
        "raw_province_code",
        "insurance_drug_code",
        "enterprise_code_raw",
        "hospital_level_detail_raw",
        "drug_code_match_flag",
        "drug_code_conflict_flag",
        "mapping_failure_reason",
    ]:
        assert column in audit.columns


def test_frozen_status_mapping_updates():
    mapping = order_status_lifecycle_map_dataframe()
    delivered = map_status_lifecycle_value("配送完成", mapping)
    assert delivered["order_phase_code"] == 60
    assert delivered["delivery_state_code"] == 5
    assert delivered["order_terminal_flag"] == 1
    assert bool(delivered["needs_manual_review"]) is False
    proof = map_status_lifecycle_value("已下发网采证明", mapping)
    assert proof["order_phase_code"] == 20
    assert proof["delivery_state_code"] == 1
    assert proof["order_terminal_flag"] == 0
    assert bool(proof["needs_manual_review"]) is False


def test_numeric_report_has_no_unit_price_or_purchase_price_consistency(tmp_path):
    raw_path = _write_raw(tmp_path)
    result = run_bs_agent_dingdan_cleaning_pipeline(
        raw_cache_path=raw_path,
        output_dir=tmp_path / "exports",
    )
    report = Path(result["output_paths"]["numeric_desensitization_report_v2"]).read_text(
        encoding="utf-8-sig"
    )
    assert "price_from_amount_quantity" not in report
    assert "purchase_price_consistency" not in report


def test_gitignore_keeps_generated_outputs_ignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in ["data/01_raw/*", "exports/clean/*", "exports/eda/*", "*.parquet", "*.csv", "*.joblib"]:
        assert pattern in gitignore
