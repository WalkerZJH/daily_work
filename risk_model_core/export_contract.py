"""Export contract declarations for risk result reports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import datetime as dt


@dataclass(frozen=True, slots=True)
class ReportExportManifest:
    report_id: str
    report_type: str
    source_batch_id: str
    html_template_id: str
    payload_json_path: str
    attachment_table_paths: list[str]
    export_formats_supported: list[str]
    generated_at: str
    export_status: str


def build_export_manifest(batch_dir: str | Path, report_id: str, report_type: str = "monthly") -> ReportExportManifest:
    batch = Path(batch_dir)
    return ReportExportManifest(
        report_id=report_id,
        report_type=report_type,
        source_batch_id=batch.name.replace("batch_id=", ""),
        html_template_id="manufacturer_monthly_risk_report_v1",
        payload_json_path=str(batch / "page_payloads" / "monthly_report_payload.json"),
        attachment_table_paths=[str(batch / "risk_entities.parquet"), str(batch / "risk_cards.parquet"), str(batch / "risk_card_evidence.parquet")],
        export_formats_supported=["html", "markdown", "csv_bundle", "future_pdf", "future_xlsx"],
        generated_at=dt.datetime.now(dt.UTC).isoformat(),
        export_status="structure_ready_no_pdf_generated",
    )

