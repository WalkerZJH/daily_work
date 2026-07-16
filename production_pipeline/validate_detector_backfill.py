"""Validate complete date-by-Detector coverage without loading full result frames."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from risk_algorithm_core.detector_config import load_daily_detector_config
from risk_model_core.repositories import CompositeDetectorResultRepository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a formal Daily Detector date-range backfill.")
    parser.add_argument("--batch-root", default="data/project_result_batches")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--source-batch-id", required=True)
    parser.add_argument("--required-run-prefix", required=True)
    parser.add_argument("--detector-config", default="configs/risk_algorithm_core/daily_detector_rules.yaml")
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--report-md", required=True)
    args = parser.parse_args(argv)

    root = Path(args.batch_root)
    dates = [value.date().isoformat() for value in pd.date_range(args.start_date, args.end_date, freq="D")]
    config = load_daily_detector_config(args.detector_config)
    expected_detectors = config.runnable_detector_ids()
    issues: list[str] = []
    component_rows: list[dict[str, object]] = []

    for observation_date in dates:
        partition = root / f"detector_run_date={observation_date}"
        try:
            repository = CompositeDetectorResultRepository(partition)
        except FileNotFoundError:
            issues.append(f"missing date partition: {observation_date}")
            continue
        selected = {
            path.parent.name.removeprefix("detector_id="): path
            for path in repository.component_batch_dirs
        }
        missing = sorted(set(expected_detectors) - set(selected))
        unexpected = sorted(set(selected) - set(expected_detectors))
        if missing:
            issues.append(f"{observation_date} missing detectors: {missing}")
        if unexpected:
            issues.append(f"{observation_date} unexpected selected detectors: {unexpected}")
        for detector_id in expected_detectors:
            batch = selected.get(detector_id)
            if batch is None:
                continue
            manifest = _json(batch / "manifest.json")
            validation = _json(batch / "detector_validation_report.json")
            if args.required_run_prefix not in batch.name:
                issues.append(f"{observation_date}/{detector_id} selected outside required run prefix: {batch.name}")
            expected_version = config.detector_version(detector_id)
            checks = {
                "report_type": manifest.get("report_type") == "daily_detector_component",
                "observation_date": manifest.get("observation_date") == observation_date,
                "detector_id": manifest.get("detector_id") == detector_id,
                "detector_version": manifest.get("detector_version") == expected_version,
                "source_batch": manifest.get("source_cleaned_input_batch_id") == args.source_batch_id,
                "engineering_gate": manifest.get("engineering_gate_status") == "passed",
                "config_policy": manifest.get("config_policy_status") == "admin_only_read_only",
                "parameter_source": manifest.get("parameter_source") == "admin_parameter_table",
                "parameter_editable": manifest.get("parameter_editable") is False,
                "config_missing": int(validation.get("config_missing_count") or 0) == 0,
            }
            declared = manifest.get("detector_tables") or {}
            checks["tables_exist"] = all(
                isinstance(relative, str) and (batch / relative).is_file()
                for relative in declared.values()
            ) and bool(declared)
            failed = sorted(name for name, passed in checks.items() if not passed)
            if failed:
                issues.append(f"{observation_date}/{detector_id} failed checks: {failed}")
            component_rows.append({
                "observation_date": observation_date,
                "detector_id": detector_id,
                "detector_version": expected_version,
                "batch_id": manifest.get("batch_id"),
                "result_count": int(validation.get("result_count") or 0),
                "clue_count": int(validation.get("clue_count") or 0),
                "manufacturer_count": int(validation.get("manufacturer_count") or 0),
                "config_missing_count": int(validation.get("config_missing_count") or 0),
            })

    components = pd.DataFrame(component_rows)
    detector_summaries = []
    for detector_id in expected_detectors:
        rows = components.loc[components.get("detector_id", pd.Series(dtype=str)).eq(detector_id)]
        detector_summaries.append({
            "detector_id": detector_id,
            "expected_dates": len(dates),
            "published_dates": int(rows["observation_date"].nunique()) if not rows.empty else 0,
            "result_count": int(rows["result_count"].sum()) if not rows.empty else 0,
            "clue_count": int(rows["clue_count"].sum()) if not rows.empty else 0,
            "min_daily_clue_count": int(rows["clue_count"].min()) if not rows.empty else 0,
            "max_daily_clue_count": int(rows["clue_count"].max()) if not rows.empty else 0,
            "config_missing_count": int(rows["config_missing_count"].sum()) if not rows.empty else 0,
        })
    expected_components = len(dates) * len(expected_detectors)
    payload = {
        "stage": "daily_detector_backfill_validation",
        "status": "passed" if not issues and len(components) == expected_components else "failed",
        "start_date": dates[0],
        "end_date": dates[-1],
        "observation_date_count": len(dates),
        "detector_count": len(expected_detectors),
        "expected_component_count": expected_components,
        "selected_component_count": int(len(components)),
        "total_result_count": int(components["result_count"].sum()) if not components.empty else 0,
        "total_clue_count": int(components["clue_count"].sum()) if not components.empty else 0,
        "source_cleaned_input_batch_id": args.source_batch_id,
        "required_run_prefix": args.required_run_prefix,
        "detectors": detector_summaries,
        "issues": issues,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    json_path = Path(args.report_json)
    md_path = Path(args.report_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "passed" else 1


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _markdown(payload: dict) -> str:
    lines = [
        "# 2025 Daily Detector 全年回填验收",
        "",
        f"- 状态：`{payload['status']}`",
        f"- 日期：`{payload['start_date']}` 至 `{payload['end_date']}`（{payload['observation_date_count']} 天）",
        f"- Detector：{payload['detector_count']} 个",
        f"- Component：{payload['selected_component_count']} / {payload['expected_component_count']}",
        f"- 结果行：{payload['total_result_count']}",
        f"- 命中行：{payload['total_clue_count']}",
        f"- 清洗输入：`{payload['source_cleaned_input_batch_id']}`",
        "",
        "| Detector | 日期 | 结果行 | 命中行 | 单日最少命中 | 单日最多命中 | config missing |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in payload["detectors"]:
        lines.append(
            f"| {item['detector_id']} | {item['published_dates']} / {item['expected_dates']} | "
            f"{item['result_count']} | {item['clue_count']} | {item['min_daily_clue_count']} | "
            f"{item['max_daily_clue_count']} | {item['config_missing_count']} |"
        )
    lines.extend(["", "## 问题", ""])
    lines.extend(f"- {issue}" for issue in payload["issues"])
    if not payload["issues"]:
        lines.append("- 无。")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
