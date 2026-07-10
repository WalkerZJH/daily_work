from __future__ import annotations

from pathlib import Path


def formal_observation_batch_root() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "project_result_batches"
    )


def formal_observation_batch_dir(report_month: str = "2025-12") -> Path:
    return (
        formal_observation_batch_root()
        / f"report_month={report_month}"
        / f"batch_id={report_month}-monthly-risk-algorithm-formal-v2-raw"
    )


def configure_formal_observation_env(monkeypatch, *, legacy_report_month: str = "2025-12") -> None:
    root = formal_observation_batch_root()
    monkeypatch.setenv("RISK_RESULT_BATCH_ROOT", str(root))
    monkeypatch.setenv("RISK_RESULT_BATCH_DIR", str(formal_observation_batch_dir(legacy_report_month)))
    monkeypatch.delenv("ALLOW_MOCK_PAYLOADS", raising=False)
