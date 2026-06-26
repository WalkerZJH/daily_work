#!/usr/bin/env python
"""Rebuild the BS_Agent_DingDan cleaning notebook as orchestration-only JSON."""

from __future__ import annotations

import json
from pathlib import Path


def md(cells: list[dict], source: str) -> None:
    cells.append({"cell_type": "markdown", "metadata": {}, "source": source.splitlines(True)})


def code(cells: list[dict], source: str) -> None:
    cells.append(
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": source.splitlines(True),
        }
    )


def build_notebook() -> dict:
    cells: list[dict] = []
    md(
        cells,
        "# BS_Agent_DingDan EDA 与清洗规则沉淀\n\n"
        "This notebook is orchestration-only. Function code lives in "
        "`src/alg/cleaning/bs_agent_dingdan.py`.",
    )
    md(
        cells,
        "## 0. 环境与路径配置\n\n"
        "Configure read mode and paths. Modes: `sql_sample`, "
        "`sql_full_to_parquet`, `parquet`.",
    )
    code(
        cells,
        '''from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path.cwd()
if PROJECT_ROOT.name == "notebooks":
    PROJECT_ROOT = PROJECT_ROOT.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from alg.cleaning.bs_agent_dingdan import (
    analyze_drug_code_consistency,
    analyze_enterprise,
    analyze_hospital_level,
    analyze_identifiers,
    analyze_numeric_desensitization,
    analyze_return_void,
    analyze_status,
    build_clean_table,
    build_column_maps,
    build_drug_category_map,
    build_ownership_map,
    build_paths,
    build_quality_report,
    build_region_mapping,
    ensure_output_dirs,
    load_env,
    load_input_dataframe,
    load_yaml,
    save_basic_profile,
    save_clean_outputs,
    save_data_source_and_order_name_profiles,
    save_quality_report,
)

pd.set_option("display.max_columns", 120)
pd.set_option("display.width", 180)

mode = "sql_sample"  # sql_sample | sql_full_to_parquet | parquet
max_rows = 5000
chunksize = 50000

paths = build_paths(PROJECT_ROOT)
ensure_output_dirs(paths)
schema = load_yaml(paths.config_path)
status_map = load_yaml(paths.status_map_path)
hospital_level_map = load_yaml(paths.hospital_level_map_path)
raw_to_alias, alias_to_raw, raw_columns = build_column_maps(schema)
sql_database_url, sql_table = load_env(paths.project_root)

print(f"project_root={paths.project_root}")
print(f"mode={mode}, max_rows={max_rows}, table={sql_table}")
print("SQL_DATABASE_URL configured:", bool(sql_database_url))''',
    )
    md(cells, "## 读取数据\n\nCSV is only a small-sample fallback. Full local cache should be Parquet.")
    code(
        cells,
        """df_raw = load_input_dataframe(
    mode=mode,
    paths=paths,
    sql_database_url=sql_database_url,
    sql_table=sql_table,
    raw_columns=raw_columns,
    max_rows=max_rows,
    chunksize=chunksize,
)
df_raw.head()""",
    )
    sections = [
        ("## 1. 基础规模检查", "basic_summary, field_counts = save_basic_profile(df_raw, alias_to_raw, paths.export_eda)\nbasic_summary, field_counts.head(20)"),
        ("## 2. 唯一标识符检查", "id_report, duplicate_samples = analyze_identifiers(df_raw, alias_to_raw, paths.export_eda)\nid_report, duplicate_samples.head()"),
        ("## 3. 数据来源与订单名称", "source_top, order_name_top = save_data_source_and_order_name_profiles(df_raw, alias_to_raw, paths.export_eda)\nsource_top.head(), order_name_top.head()"),
        ("## 4. 地区字段清洗", "region_map, region_conflicts = build_region_mapping(df_raw, alias_to_raw, paths.export_eda, paths.export_mappings)\nregion_map.head(), region_conflicts.head()"),
        ("## 5. 药品编码与医保编码一致性", "drug_code_report = analyze_drug_code_consistency(df_raw, alias_to_raw, paths.export_eda)\ndrug_code_report"),
    ]
    for title, body in sections:
        md(cells, title)
        code(cells, body)
    md(
        cells,
        "## 6. 数值字段脱敏影响检查\n\n"
        "Updated policy: quantity fields share multiplier q; amount fields share "
        "multiplier m. `delivery_rate`, `arrival_rate`, `overall_arrival_rate`, "
        "quantity trends, amount trends, and order frequency trends are allowed. "
        "`price_from_amount_quantity` is forbidden: do not infer real unit price "
        "from amount / quantity.",
    )
    code(cells, "numeric_report = analyze_numeric_desensitization(df_raw, alias_to_raw, paths.export_eda)\nnumeric_report")
    remaining = [
        ("## 7. 订单状态枚举与初步归类", "status_counts, status_review, status_unmapped = analyze_status(\n    df_raw, alias_to_raw, status_map, paths.export_eda, paths.export_mappings\n)\nstatus_counts.head(), status_review.head(), status_unmapped.head()"),
        ("## 8. 医疗机构等级清洗", "hospital_counts, hospital_review, hospital_unmapped = analyze_hospital_level(\n    df_raw, alias_to_raw, hospital_level_map, paths.export_eda, paths.export_mappings\n)\nhospital_counts.head(), hospital_review.head(), hospital_unmapped.head()"),
        ("## 9. 企业字段关系检查", "enterprise_report = analyze_enterprise(df_raw, alias_to_raw, paths.export_eda)\nenterprise_report"),
        ("## 10. 药品类别编码", "drug_category_counts = build_drug_category_map(df_raw, alias_to_raw, paths.export_mappings)\ndrug_category_counts.head()"),
        ("## 11. 所有制形式编码", "ownership_map = build_ownership_map(df_raw, alias_to_raw, paths.export_mappings)\nownership_map.head()"),
        ("## 12. 退回数量与作废数量", "return_void_report = analyze_return_void(df_raw, alias_to_raw, paths.export_eda)\nreturn_void_report"),
        ("## 13. 生成 clean 表", "df_clean = build_clean_table(\n    df_raw,\n    schema=schema,\n    raw_to_alias=raw_to_alias,\n    status_map=status_map,\n    hospital_level_map=hospital_level_map,\n    drug_category_counts=drug_category_counts,\n)\nsave_clean_outputs(df_clean, paths)\ndf_clean.head()"),
        ("## 14. 生成 Markdown 数据质量报告", "quality_report = build_quality_report(\n    schema=schema,\n    basic=basic_summary,\n    status_review=status_review,\n    status_unmapped=status_unmapped,\n    hospital_review=hospital_review,\n    hospital_unmapped=hospital_unmapped,\n)\nreport_path = save_quality_report(quality_report, paths.export_eda)\nprint(report_path)\nprint(quality_report[:1000])"),
    ]
    for title, body in remaining:
        md(cells, title)
        code(cells, body)
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python (alg-ml)",
                "language": "python",
                "name": "alg-ml",
            },
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "notebooks/01_BS_Agent_DingDan_EDA_and_Cleaning.ipynb"
    output.write_text(json.dumps(build_notebook(), ensure_ascii=True, indent=1), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
