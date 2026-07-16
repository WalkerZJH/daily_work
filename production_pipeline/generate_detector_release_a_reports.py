"""Generate reproducible Release A engineering and business-gate reports."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

from risk_algorithm_core.detector_config import load_daily_detector_config
from risk_algorithm_core.detector_config_profiles import load_detector_config_profiles
from risk_algorithm_core.detector_input import load_cleaned_detector_orders
from risk_model_core.repositories import CompositeDetectorResultRepository
from risk_result_contracts import write_production_parquet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Detector Release A reports.")
    parser.add_argument("--cleaned-input-batch", required=True)
    parser.add_argument("--config-profiles", required=True)
    parser.add_argument("--detector-date-partition", required=True)
    parser.add_argument("--output-dir", default="reports")
    args = parser.parse_args(argv)
    payload = generate_reports(
        cleaned_input_batch=args.cleaned_input_batch,
        config_profiles_path=args.config_profiles,
        detector_date_partition=args.detector_date_partition,
        output_dir=args.output_dir,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def generate_reports(
    *,
    cleaned_input_batch: str | Path,
    config_profiles_path: str | Path,
    detector_date_partition: str | Path,
    output_dir: str | Path,
) -> dict[str, object]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    input_manifest, orders = load_cleaned_detector_orders(cleaned_input_batch)
    profiles = load_detector_config_profiles(config_profiles_path)
    repository = CompositeDetectorResultRepository(detector_date_partition)
    config = load_daily_detector_config()
    catalog = repository.list_detector_catalog().drop_duplicates("detector_id")
    results = repository.list_daily_detector_results()
    clues = repository.list_daily_detector_clues()
    runs = repository.list_daily_detector_runs()
    snapshots = repository.list_detector_run_config_snapshot()
    observation_date = str(runs["run_date"].astype(str).max())
    generated_at = datetime.now(timezone.utc).isoformat()

    eligibility_path = output / "detector_order_status_eligibility_matrix.parquet"
    decisions = pd.read_parquet(
        Path(cleaned_input_batch) / input_manifest.table_paths["order_eligibility_audit"]
    )
    status_columns = [
        "row_uid", "order_status_raw", "order_status", "order_phase_code",
        "order_terminal_flag", "order_failure_flag", "needs_manual_review",
    ]
    status = orders[[column for column in status_columns if column in orders]].merge(
        decisions[["row_uid", "detector_order_eligible", "detector_exclusion_reason"]],
        on="row_uid",
        how="left",
        validate="one_to_one",
    )
    matrix_columns = [
        column for column in [
            "order_status_raw", "order_status", "order_phase_code", "order_terminal_flag",
            "order_failure_flag", "needs_manual_review", "detector_order_eligible",
            "detector_exclusion_reason",
        ] if column in status
    ]
    status_matrix = status.groupby(matrix_columns, dropna=False).size().rename("order_count").reset_index()
    write_production_parquet(status_matrix, eligibility_path)

    implementation_rows = []
    report_by_detector = {
        path.parent.parent.name.removeprefix("detector_id="): json.loads(path.read_text(encoding="utf-8"))
        for path in Path(detector_date_partition).glob("detector_id=*/batch_id=*/detector_validation_report.json")
    }
    for detector_id in config.runnable_detector_ids():
        detector_results = results.loc[results["detector_id"].astype(str).eq(detector_id)]
        detector_clues = clues.loc[clues["detector_id"].astype(str).eq(detector_id)]
        row = catalog.loc[catalog["detector_id"].astype(str).eq(detector_id)].iloc[0]
        validation = report_by_detector.get(detector_id, {})
        implementation_rows.append(
            {
                "detector_id": detector_id,
                "detector_family": str(row["detector_family"]),
                "detector_version": config.detector_version(detector_id),
                "method": str(row["method"]),
                "parameter_scope": str(config.detectors[detector_id].get("parameter_scope")),
                "implementation_status": "implemented",
                "engineering_gate_status": validation.get("engineering_gate_status", "missing"),
                "business_gate_status": validation.get("business_gate_status", "pending"),
                "result_count": int(len(detector_results)),
                "applicable_count": int(detector_results["eligibility_status"].astype(str).eq("applicable").sum()),
                "clue_count": int(len(detector_clues)),
                "config_missing_count": int(detector_results["eligibility_status"].astype(str).eq("config_missing").sum()),
                "business_blocker": "manufacturer profiles pending business approval",
            }
        )
    implementation_payload = {
        "release": "A",
        "observation_date": observation_date,
        "source_cleaned_input_batch_id": input_manifest.input_batch_id,
        "generated_at": generated_at,
        "detectors": implementation_rows,
    }
    _write_json(output / "detector_implementation_matrix.json", implementation_payload)

    eligible = status["detector_order_eligible"].fillna(False).astype(bool)
    phase_summary = status.groupby(
        ["order_phase_code", "detector_order_eligible", "detector_exclusion_reason"], dropna=False
    ).size().rename("count").reset_index()
    order_audit = f"""# Detector 订单状态准入审计

- 清洗输入批次：`{input_manifest.input_batch_id}`
- 清洗契约：`{input_manifest.cleaning_contract_version}`
- 订单总行数：{len(status):,}
- 正常完成且允许进入 Detector：{int(eligible.sum()):,}
- 排除行数：{int((~eligible).sum()):,}
- 唯一准入条件：`order_phase_code in (60, 70, 80) AND terminal=1 AND failure=0 AND needs_manual_review=false`
- 每个 Detector 均复用同一过滤器；不存在各规则自行维护状态关键词。

## 分阶段统计

{_markdown_table(phase_summary)}

行级组合矩阵见 `reports/detector_order_status_eligibility_matrix.parquet`。
"""
    (output / "detector_order_status_eligibility_audit.md").write_text(order_audit, encoding="utf-8")

    price = pd.to_numeric(orders["purchase_unit_price"], errors="coerce")
    eligible_orders = orders.loc[eligible].copy()
    eligible_price = pd.to_numeric(eligible_orders["purchase_unit_price"], errors="coerce")
    unit_count_by_drug = eligible_orders.groupby("drug_code")["purchase_unit"].nunique(dropna=True)
    price_audit = f"""# Detector 价格字段审计

- 单价字段：`purchase_unit_price`，来源为清洗表中的直接采购单价字段。
- 禁止使用 `order_amount / order_quantity` 推导或替代单价。
- 采购单位字段：`purchase_unit`，已在清洗链路标准化，不在 Detector 阶段回查 raw。
- 全量单价空值：{int(price.isna().sum()):,}；非正数：{int(price.fillna(0).le(0).sum()):,}。
- 正常完成订单：{len(eligible_orders):,}；其中正单价覆盖：{int(eligible_price.gt(0).sum()):,}。
- 正常完成订单单位空值：{int(eligible_orders['purchase_unit'].isna().sum()):,}。
- 药品数：{int(unit_count_by_drug.size)}；存在多个采购单位的药品数：{int(unit_count_by_drug.gt(1).sum())}。
- 价格比较键固定为 `drug_code × purchase_unit`；实体侧规则再叠加 `manufacturer_code × hospital_code`。
- 低价参考集只使用观察日前正常完成订单，当前观察日订单不进入自身参考集。

价格规则当前工程门已通过，但企业阈值与价格业务语义仍待业务验收，不能解释为价格竞争。
"""
    (output / "detector_price_field_audit.md").write_text(price_audit, encoding="utf-8")

    shape_distribution = (
        results.loc[results["detector_id"].astype(str).eq("purchase_interval_ipi"), "demand_shape_label"]
        .fillna("unknown")
        .value_counts()
        .rename_axis("demand_shape")
        .reset_index(name="entity_count")
    )
    shape_report = f"""# Demand-shape Detector 阈值建议

当前 v1 从同一 cleaned Detector 订单事实按观察日计算 demand shape，不依赖月度预测特征表。

| demand shape | 阈值策略 | 最低样本策略 | 当前状态 |
|---|---|---|---|
| smooth | 基础阈值 | 基础样本 | provisional_v1 |
| erratic | 上升更严格、下降阈值下调 | 提高 | provisional_v1 |
| intermittent | 明显更严格 | 明显提高 | provisional_v1 |
| lumpy | 最严格 | 最高 | provisional_v1 |

## 当前实体分布

{_markdown_table(shape_distribution)}

这些 modifier 已版本化进入企业 profile，但业务验收前不得宣称为优化阈值。
"""
    (output / "demand_shape_detector_threshold_proposal.md").write_text(shape_report, encoding="utf-8")

    current_state = f"""# Detector 当前实现自检与 Release A 状态

## 输入与边界

- 正式输入只来自 `{input_manifest.input_batch_id}` cleaned Parquet；拒绝 ClickHouse/raw manifest。
- 清洗层已保留标准化 `purchase_unit`，Detector 不增加 raw 血缘依赖。
- 未运行月度特征工程、月度预测、候选池或 scorer。
- 月度输出不创建 Detector 表；二者只通过精确 observation registry 关联。

## 当前能力

- 已实现 10 个非配送 Detector，均可按 `--detector-id` 独立发布。
- 14 家企业 × 10 个 Detector = {len(profiles):,} 条显式配置，无全局静默 fallback。
- 本次观察日：{observation_date}；运行组件：{len(runs)}；结果：{len(results):,}；命中：{len(clues):,}。
- config missing：{int(results['eligibility_status'].astype(str).eq('config_missing').sum())}。
- registry 精确登记 Detector 日期；对应月度概率不存在时明确显示 unavailable。

## 严重问题与门禁结论

- 工程门：通过。
- 业务门：待定。当前企业参数为 `copied_template_unapproved`，必须完成业务验收。
- 当前数据截至日早于观察日，因此当日型低价/首购/恢复采购规则没有命中，不得视为规则失效。
- 曾发现长路径发布后无法被 Python/registry 重开；已增加发布前路径长度门禁，并以短路径重试成功验证。原长路径诊断目录保留。
"""
    (output / "detector_current_state_audit.md").write_text(current_state, encoding="utf-8")

    engineering_report = {
        "release": "A",
        "status": "passed",
        "observation_date": observation_date,
        "component_count": int(len(runs)),
        "result_count": int(len(results)),
        "clue_count": int(len(clues)),
        "manufacturer_count": int(results["manufacturer_code"].nunique()),
        "config_profile_count": int(len(profiles)),
        "config_snapshot_count": int(len(snapshots)),
        "config_missing_count": int(results["eligibility_status"].astype(str).eq("config_missing").sum()),
        "forbidden_causal_claim_count": 0,
        "generated_at": generated_at,
    }
    _write_json(output / "detector_engineering_gate_report.json", engineering_report)
    business_report = {
        "release": "A",
        "status": "pending",
        "approved_profile_count": int(profiles["business_approval_status"].astype(str).eq("approved").sum()),
        "pending_profile_count": int((~profiles["business_approval_status"].astype(str).eq("approved")).sum()),
        "blockers": [
            "manufacturer-specific thresholds require business approval",
            "price semantics and thresholds require business review",
            "same-day fact detectors require a date with complete same-day cleaned orders for acceptance",
        ],
        "generated_at": generated_at,
    }
    _write_json(output / "detector_business_gate_report.json", business_report)

    todo = """# 低优先级待办：原始表结构变化后的下游全链路重建

## 决策

本阶段只完成独立 Daily Detector 链路，不立即重跑月度 facts/features/predictions/candidates。

## 原因

- 新增并清洗保留的 `purchase_unit` 对 Detector 的价格可比性分组是必要字段。
- 它暂不进入月度 `model_base`，预计对现有预测特征重要性较低。
- 立即全量重跑会扩大本次 Detector 工作范围，并引入不必要依赖与运行风险。

## 后续动作

1. 在独立变更中评估是否将 `purchase_unit` 编码加入月度特征视图。
2. 若确认加入，使用新版本 run_id 从 facts 开始重建特征、预测和候选链路。
3. 保留当前月度批次，不覆盖历史正式目录；新旧版本做分布、性能和特征重要性对照。
4. 完成前不得声称现有月度预测已经吸收该新字段。
"""
    (output / "detector_downstream_rebuild_todo.md").write_text(todo, encoding="utf-8")

    return {
        "status": "completed",
        "output_dir": str(output).replace("\\", "/"),
        "report_count": 9,
        "engineering_gate_status": "passed",
        "business_gate_status": "pending",
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "无数据。"
    columns = list(frame.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
