# Export Readiness for Reports

- formal PDF generated: false.
- current output: HTML/Markdown-ready payload plus parquet/csv bundle.
- PDF should be rendered by backend or frontend distribution layer.
- export formats supported: html, markdown, csv_bundle, future_pdf, future_xlsx.

```json
{
  "report_id": "report_2025-12-business-detector-v1",
  "report_type": "monthly",
  "source_batch_id": "2025-12-business-detector-v1",
  "html_template_id": "manufacturer_monthly_report_v1",
  "payload_json_path": "C:\\Users\\admin\\Myprojects\\for_git\\algo_main\\data\\entity_complete_v2_coverage_expansion\\11_business_detector_adaptation\\risk_result_batches\\batch_id=2025-12-business-detector-v1\\page_payloads\\monthly_report_payload.json",
  "attachment_table_paths": [
    "C:\\Users\\admin\\Myprojects\\for_git\\algo_main\\data\\entity_complete_v2_coverage_expansion\\11_business_detector_adaptation\\risk_result_batches\\batch_id=2025-12-business-detector-v1\\risk_entities.parquet",
    "C:\\Users\\admin\\Myprojects\\for_git\\algo_main\\data\\entity_complete_v2_coverage_expansion\\11_business_detector_adaptation\\risk_result_batches\\batch_id=2025-12-business-detector-v1\\risk_cards.parquet",
    "C:\\Users\\admin\\Myprojects\\for_git\\algo_main\\data\\entity_complete_v2_coverage_expansion\\11_business_detector_adaptation\\risk_result_batches\\batch_id=2025-12-business-detector-v1\\risk_card_evidence.parquet"
  ],
  "export_formats_supported": [
    "html",
    "markdown",
    "csv_bundle",
    "future_pdf",
    "future_xlsx"
  ],
  "generated_at": "2026-07-07T09:53:23.263891",
  "export_status": "structure_ready_no_pdf_generated"
}
```
