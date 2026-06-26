#!/usr/bin/env python
"""Rebuild the BS_Agent_DingDan v2 pipeline review notebook."""

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
        "# BS_Agent_DingDan v2 清洗 Pipeline 复核\n\n"
        "本 notebook 仅用于 BS_Agent_DingDan v2 清洗 pipeline 的人工复核与汇报展示。\n\n"
        "正式清洗逻辑统一来自 "
        "`alg.cleaning.bs_agent_dingdan_pipeline.run_bs_agent_dingdan_cleaning_pipeline`。\n\n"
        "notebook 不再维护独立清洗逻辑。",
    )
    md(cells, "## 1. 环境与路径配置")
    code(
        cells,
        '''from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path.cwd()
if PROJECT_ROOT.name == "notebooks":
    PROJECT_ROOT = PROJECT_ROOT.parent

SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from alg.cleaning.bs_agent_dingdan_pipeline import run_bs_agent_dingdan_cleaning_pipeline
from alg.cleaning.bs_agent_dingdan import load_env

pd.set_option("display.max_columns", 120)
pd.set_option("display.width", 180)

sql_database_url, sql_table = load_env(PROJECT_ROOT)

sample_mode = True
max_rows = 5000
output_format = "parquet"
generate_model = True
generate_quality_report = True
generate_clean = True
generate_audit = True
return_dataframes = True

print(f"project_root={PROJECT_ROOT}")
print(f"sample_mode={sample_mode}, max_rows={max_rows}, table={sql_table}")
print("SQL_DATABASE_URL configured:", bool(sql_database_url))''',
    )
    md(cells, "## 2. 运行 pipeline")
    code(
        cells,
        '''result = run_bs_agent_dingdan_cleaning_pipeline(
    sql_database_url=sql_database_url,
    table_name=sql_table,
    output_dir="exports",
    output_format=output_format,
    max_rows=max_rows,
    sample_mode=sample_mode,
    generate_model=generate_model,
    generate_clean=generate_clean,
    generate_audit=generate_audit,
    generate_quality_report=generate_quality_report,
    return_dataframes=return_dataframes,
)

result["row_count"], result["model_columns"], result["output_paths"]''',
    )
    md(cells, "## 3. 展示三张核心表")
    code(
        cells,
        '''clean_v2 = result["dataframes"]["clean"]
model_base = result["dataframes"]["model_base"]
audit = result["dataframes"]["audit"]

display(clean_v2.head())
display(model_base.head())
display(audit.head())

clean_v2.shape, model_base.shape, audit.shape''',
    )
    md(cells, "## 4. model_base 字段检查")
    code(
        cells,
        '''model_base.columns.tolist()

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
sorted(forbidden.intersection(model_base.columns))''',
    )
    md(cells, "## 5. 主键检查")
    code(
        cells,
        '''{
    "clean_row_uid_unique": clean_v2["row_uid"].is_unique,
    "model_row_uid_unique": model_base["row_uid"].is_unique,
    "audit_row_uid_unique": audit["row_uid"].is_unique,
    "clean_order_detail_id_unique": clean_v2["order_detail_id"].is_unique,
    "model_order_detail_id_unique": model_base["order_detail_id"].is_unique,
    "audit_order_detail_id_unique": audit["order_detail_id"].is_unique,
}''',
    )
    md(cells, "## 6. 订单状态映射检查")
    code(
        cells,
        '''display(clean_v2["order_phase_code"].value_counts(dropna=False).sort_index())
display(clean_v2["delivery_state_code"].value_counts(dropna=False).sort_index())
display(clean_v2["needs_manual_review"].value_counts(dropna=False))

display(pd.read_csv(PROJECT_ROOT / "exports/eda/order_status_mapping_coverage.csv"))
display(pd.read_csv(PROJECT_ROOT / "exports/eda/order_status_suspicious_mapping.csv"))''',
    )
    md(cells, "## 7. 药品编码与地区检查")
    code(
        cells,
        '''display(audit["drug_code_match_flag"].value_counts(dropna=False))
display(audit["drug_code_conflict_flag"].value_counts(dropna=False))
display(clean_v2["region_dirty_flag"].value_counts(dropna=False))''',
    )
    md(cells, "## 8. 数值脱敏与矛盾检查")
    code(
        cells,
        '''numeric_report = pd.read_csv(PROJECT_ROOT / "exports/eda/numeric_desensitization_report_v2.csv")
display(numeric_report.head(50))

display(numeric_report[numeric_report["metric_group"] == "status_quantity_contradiction"])''',
    )
    md(cells, "## 9. 质量报告展示")
    code(
        cells,
        '''quality_report_path = PROJECT_ROOT / "exports/eda/bs_agent_dingdan_quality_report_v2.md"
print(quality_report_path.read_text(encoding="utf-8")[:3000])''',
    )
    md(
        cells,
        "## 10. 汇报结论\n\n"
        "- 本 notebook 调用正式 v2 pipeline 生成 model_base。\n"
        "- model_base 是建模基础表，不是最终 X_train。\n"
        "- clean/audit 仅用于人工复核。\n"
        "- `delivery_rate`、`arrival_rate` 等 ratio 字段来自数量/金额比例，不代表时间。\n"
        "- 状态字段后续进入算法时必须按 cutoff 聚合，避免泄漏。",
    )
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
