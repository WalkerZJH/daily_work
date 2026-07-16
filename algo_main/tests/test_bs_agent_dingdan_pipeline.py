from pathlib import Path

import pandas as pd
import pytest

from alg.cleaning.bs_agent_dingdan import (
    map_unique_text_values_to_frame,
    map_status_lifecycle_value,
    order_status_lifecycle_map_dataframe,
)
import alg.cleaning.bs_agent_dingdan_pipeline as pipeline_module
from alg.cleaning.bs_agent_dingdan_pipeline import run_bs_agent_dingdan_cleaning_pipeline


ROOT = Path(__file__).resolve().parents[1]
MODEL_BASE_PATH = ROOT / "data/03_cleaned/bs_agent_dingdan_model_base.parquet"


@pytest.fixture(autouse=True)
def cleanup_model_base_output():
    MODEL_BASE_PATH.unlink(missing_ok=True)
    yield
    MODEL_BASE_PATH.unlink(missing_ok=True)


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
                "采购单位": " 盒 ",
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
                "采购单位": "盒",
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


def _write_small_raw(tmp_path: Path) -> Path:
    raw_path = tmp_path / "raw.parquet"
    _raw_sample().head(1).to_parquet(raw_path, index=False)
    return raw_path


def test_pipeline_function_importable():
    assert callable(run_bs_agent_dingdan_cleaning_pipeline)


def test_pipeline_default_writes_model_and_report_only(tmp_path):
    raw_path = _write_raw(tmp_path)
    result = run_bs_agent_dingdan_cleaning_pipeline(
        raw_cache_path=raw_path,
        output_dir=tmp_path / "exports",
        max_rows=2,
    )
    paths = result["output_paths"]
    expected_model_path = MODEL_BASE_PATH
    assert Path(paths["model_base"]["parquet"]) == expected_model_path
    assert expected_model_path.exists()
    assert not (tmp_path / "exports/clean/bs_agent_dingdan_model_base.parquet").exists()
    assert Path(paths["review_outputs"]["quality_report"]).exists()
    assert "clean_sample_v2" not in paths["review_outputs"]
    assert "audit_sample" not in paths["review_outputs"]


def test_pipeline_reuse_if_enough_refreshes_small_cache(tmp_path, monkeypatch):
    raw_path = _write_small_raw(tmp_path)

    def fake_read_sql(**kwargs):
        return _raw_sample()

    monkeypatch.setattr(pipeline_module, "_read_sql_projected", fake_read_sql)
    result = run_bs_agent_dingdan_cleaning_pipeline(
        raw_cache_path=raw_path,
        output_dir=tmp_path / "exports",
        max_rows=2,
        cache_policy="reuse_if_enough",
    )
    assert result["row_count"] == 2
    metadata = pipeline_module._read_cache_meta(raw_path)
    assert metadata["row_count"] == 2
    assert metadata["max_rows"] == 2


def test_pipeline_always_reuse_cache_even_when_smaller_than_max_rows(tmp_path, monkeypatch):
    raw_path = _write_small_raw(tmp_path)

    def fail_if_sql_called(**kwargs):
        raise AssertionError("SQL should not be called when cache_policy=always_reuse")

    monkeypatch.setattr(pipeline_module, "_read_sql_projected", fail_if_sql_called)
    result = run_bs_agent_dingdan_cleaning_pipeline(
        raw_cache_path=raw_path,
        output_dir=tmp_path / "exports",
        max_rows=2,
        cache_policy="always_reuse",
    )
    assert result["row_count"] == 1


def test_pipeline_no_use_cache_forces_sql_read(tmp_path, monkeypatch):
    raw_path = _write_small_raw(tmp_path)

    def fake_read_sql(**kwargs):
        return _raw_sample()

    monkeypatch.setattr(pipeline_module, "_read_sql_projected", fake_read_sql)
    result = run_bs_agent_dingdan_cleaning_pipeline(
        raw_cache_path=raw_path,
        output_dir=tmp_path / "exports",
        max_rows=1,
        use_cache=False,
    )
    assert result["row_count"] == 2


def test_pipeline_refresh_cache_overrides_reuse(tmp_path, monkeypatch):
    raw_path = _write_raw(tmp_path)

    def fake_read_sql(**kwargs):
        return _raw_sample().head(1)

    monkeypatch.setattr(pipeline_module, "_read_sql_projected", fake_read_sql)
    result = run_bs_agent_dingdan_cleaning_pipeline(
        raw_cache_path=raw_path,
        output_dir=tmp_path / "exports",
        max_rows=2,
        refresh_cache=True,
    )
    assert result["row_count"] == 1
    assert result["cache_policy"] == "refresh"


def test_pipeline_optional_clean_and_audit_outputs(tmp_path):
    raw_path = _write_raw(tmp_path)
    result = run_bs_agent_dingdan_cleaning_pipeline(
        raw_cache_path=raw_path,
        output_dir=tmp_path / "exports",
        max_rows=2,
        generate_clean=True,
        generate_audit=True,
    )
    review_outputs = result["output_paths"]["review_outputs"]
    assert Path(review_outputs["clean_sample_v2"]) == tmp_path / "exports/clean/bs_agent_dingdan_clean_sample_v2.csv"
    assert Path(review_outputs["clean_sample_v2"]).exists()
    assert Path(review_outputs["audit_sample"]) == tmp_path / "exports/clean/bs_agent_dingdan_audit_sample.csv"
    assert Path(review_outputs["audit_sample"]).exists()


def test_pipeline_model_and_audit_columns(tmp_path):
    raw_path = _write_raw(tmp_path)
    result = run_bs_agent_dingdan_cleaning_pipeline(
        raw_cache_path=raw_path,
        output_dir=tmp_path / "exports",
        max_rows=2,
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
    assert "purchase_unit" not in model.columns
    audit = pd.read_csv(result["output_paths"]["review_outputs"]["audit_sample"])
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


def test_cleaned_output_retains_normalized_purchase_unit_without_adding_it_to_model_base(tmp_path):
    raw_path = _write_raw(tmp_path)
    result = run_bs_agent_dingdan_cleaning_pipeline(
        raw_cache_path=raw_path,
        output_dir=tmp_path / "exports",
        max_rows=2,
        generate_clean=True,
    )
    clean = pd.read_csv(result["output_paths"]["review_outputs"]["clean_sample_v2"])
    model = pd.read_parquet(result["output_paths"]["model_base"]["parquet"])
    assert clean["purchase_unit"].tolist() == ["盒", "盒"]
    assert "purchase_unit" not in model.columns


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


def test_large_cleaning_mapping_evaluates_only_distinct_text_values():
    values = pd.Series(["配送完成"] * 50_000 + ["已下发网采证明"] * 50_000)
    calls: list[str] = []

    def mapper(value):
        calls.append(value)
        return pd.Series({"mapped": value})

    mapped = map_unique_text_values_to_frame(values, mapper)
    assert calls == ["配送完成", "已下发网采证明"]
    assert len(mapped) == 100_000
    assert mapped.iloc[0]["mapped"] == "配送完成"
    assert mapped.iloc[-1]["mapped"] == "已下发网采证明"


def test_numeric_report_has_no_unit_price_or_purchase_price_consistency(tmp_path):
    raw_path = _write_raw(tmp_path)
    result = run_bs_agent_dingdan_cleaning_pipeline(
        raw_cache_path=raw_path,
        output_dir=tmp_path / "exports",
        max_rows=2,
    )
    report = Path(result["output_paths"]["review_outputs"]["numeric_desensitization_report_v2"]).read_text(
        encoding="utf-8-sig"
    )
    assert "price_from_amount_quantity" not in report
    assert "purchase_price_consistency" not in report


def test_gitignore_keeps_generated_outputs_ignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in [
        "data/01_raw/*",
        "data/03_cleaned/*",
        "data/04_facts/*",
        "data/05_features/*",
        "data/06_train_sets/*",
        "exports/clean/*",
        "exports/eda/*",
        "*.parquet",
        "*.csv",
        "*.xlsx",
        "*.joblib",
        "*.pkl",
    ]:
        assert pattern in gitignore
