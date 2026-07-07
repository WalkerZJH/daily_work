"""Configuration loading for monthly production risk runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import datetime as dt
import json


@dataclass(slots=True)
class MonthlyRiskRunConfig:
    run_id: str
    report_type: str
    report_month: str
    run_date: str
    timezone: str
    cutoff_policy: str
    output_root: str
    raw_batch_dir: str
    schema_mapping_path: str | None
    tenant_id: str
    enterprise_id: str
    manufacturer_codes: list[str] | str
    primary_horizon: str
    available_horizons: list[str]
    artifact_dir: str
    artifact_alias: str
    require_artifact: bool
    worklist: dict[str, Any] = field(default_factory=dict)
    detectors: dict[str, Any] = field(default_factory=dict)
    safety: dict[str, Any] = field(default_factory=dict)
    export: dict[str, Any] = field(default_factory=dict)

    @property
    def resolved_report_month(self) -> str:
        return resolve_report_month_and_cutoff(self.report_month, self.run_date)[0]

    @property
    def resolved_cutoff_date(self) -> str:
        return resolve_report_month_and_cutoff(self.report_month, self.run_date)[1]


def load_run_config(path: str | Path) -> MonthlyRiskRunConfig:
    data = _load_mapping(Path(path))
    run = data.get("run", {})
    input_cfg = data.get("input", {})
    scope = data.get("scope", {})
    horizon = data.get("horizon", {})
    model = data.get("model", {})
    safety = data.get("safety", {})
    if safety.get("auto_dispatch_allowed") is True:
        raise ValueError("auto_dispatch_allowed must remain false.")
    if safety.get("customer_facing_probability_service_allowed") is True:
        raise ValueError("customer_facing_probability_service_allowed must remain false.")

    return MonthlyRiskRunConfig(
        run_id=str(run.get("run_id") or "auto"),
        report_type=str(run.get("report_type") or "monthly"),
        report_month=str(run.get("report_month") or "auto_previous_month"),
        run_date=str(run.get("run_date") or dt.date.today().isoformat()),
        timezone=str(run.get("timezone") or "Asia/Shanghai"),
        cutoff_policy=str(run.get("cutoff_policy") or "month_end"),
        output_root=str(run.get("output_root") or "data/risk_result_batches"),
        raw_batch_dir=str(input_cfg.get("raw_batch_dir") or ""),
        schema_mapping_path=input_cfg.get("schema_mapping_path"),
        tenant_id=str(scope.get("tenant_id") or "default_tenant"),
        enterprise_id=str(scope.get("enterprise_id") or "default_enterprise"),
        manufacturer_codes=scope.get("manufacturer_codes") or "all",
        primary_horizon=str(horizon.get("primary_horizon") or "H6"),
        available_horizons=[str(x) for x in horizon.get("available_horizons", ["H3", "H6", "H12"])],
        artifact_dir=str(model.get("artifact_dir") or "model_artifacts/risk_algorithm_core/main_churn/current"),
        artifact_alias=str(model.get("artifact_alias") or "current"),
        require_artifact=bool(model.get("require_artifact", True)),
        worklist=dict(data.get("worklist", {})),
        detectors=dict(data.get("detectors", {})),
        safety=dict(safety),
        export=dict(data.get("export", {})),
    )


def resolve_report_month_and_cutoff(report_month: str, run_date: str | None = None) -> tuple[str, str]:
    if report_month != "auto_previous_month":
        month = report_month[:7]
    else:
        today = dt.date.fromisoformat(run_date or dt.date.today().isoformat())
        first_of_month = today.replace(day=1)
        previous_last = first_of_month - dt.timedelta(days=1)
        month = previous_last.strftime("%Y-%m")
    year, mon = [int(part) for part in month.split("-")]
    if mon == 12:
        next_month = dt.date(year + 1, 1, 1)
    else:
        next_month = dt.date(year, mon + 1, 1)
    cutoff = next_month - dt.timedelta(days=1)
    return month, cutoff.isoformat()


def _load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml

        loaded = yaml.safe_load(text)
        return loaded or {}
    except ImportError:
        return _parse_simple_yaml(text)


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    # Minimal fallback for flat fixture configs. Use PyYAML in normal environments.
    result: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not raw.startswith(" ") and line.endswith(":"):
            key = line[:-1]
            result[key] = {}
            current = result[key]
        elif current is not None and ":" in line:
            key, value = line.strip().split(":", 1)
            current[key] = _coerce_scalar(value.strip())
    return result


def _coerce_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "None", ""}:
        return None
    return value
