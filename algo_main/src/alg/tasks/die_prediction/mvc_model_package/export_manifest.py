"""Export manifest helpers for future HTML/PDF/XLSX distribution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def build_export_manifest(batch_id: str, batch_dir: str | Path) -> dict[str, Any]:
    root = Path(batch_dir)
    return {
        "report_id": f"report_{batch_id}",
        "report_type": "monthly",
        "source_batch_id": batch_id,
        "html_template_id": "manufacturer_monthly_report_v1",
        "payload_json_path": str(root / "page_payloads" / "monthly_report_payload.json"),
        "attachment_table_paths": [
            str(root / "risk_entities.parquet"),
            str(root / "risk_cards.parquet"),
            str(root / "risk_card_evidence.parquet"),
        ],
        "export_formats_supported": ["html", "markdown", "csv_bundle", "future_pdf", "future_xlsx"],
        "generated_at": pd.Timestamp.now().isoformat(),
        "export_status": "structure_ready_no_pdf_generated",
    }
