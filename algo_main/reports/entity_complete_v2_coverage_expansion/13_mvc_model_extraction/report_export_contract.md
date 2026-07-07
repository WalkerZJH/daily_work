# Report Export Contract

- current output: structured result batch and HTML/Markdown-ready payloads.
- formal PDF generated: false.
- PDF/XLSX export belongs to backend/frontend distribution layer, not algorithm training layer.
- export status: structure_ready_no_pdf_generated

```json
{
  "report_id": "report_2025-12-frontend-worklist-v1",
  "report_type": "monthly",
  "source_batch_id": "2025-12-frontend-worklist-v1",
  "html_template_id": "manufacturer_monthly_report_v1",
  "payload_json_path": "C:\\Users\\admin\\Myprojects\\for_git\\algo_main\\data\\entity_complete_v2_coverage_expansion\\10_frontend_worklist_model_package\\risk_result_batches\\batch_id=2025-12-frontend-worklist-v1\\page_payloads\\monthly_report_payload.json",
  "attachment_table_paths": [
    "C:\\Users\\admin\\Myprojects\\for_git\\algo_main\\data\\entity_complete_v2_coverage_expansion\\10_frontend_worklist_model_package\\risk_result_batches\\batch_id=2025-12-frontend-worklist-v1\\risk_entities.parquet",
    "C:\\Users\\admin\\Myprojects\\for_git\\algo_main\\data\\entity_complete_v2_coverage_expansion\\10_frontend_worklist_model_package\\risk_result_batches\\batch_id=2025-12-frontend-worklist-v1\\risk_cards.parquet",
    "C:\\Users\\admin\\Myprojects\\for_git\\algo_main\\data\\entity_complete_v2_coverage_expansion\\10_frontend_worklist_model_package\\risk_result_batches\\batch_id=2025-12-frontend-worklist-v1\\risk_card_evidence.parquet"
  ],
  "export_formats_supported": [
    "html",
    "markdown",
    "csv_bundle",
    "future_pdf",
    "future_xlsx"
  ],
  "generated_at": "2026-07-07T09:21:08.536353",
  "export_status": "structure_ready_no_pdf_generated"
}
```
