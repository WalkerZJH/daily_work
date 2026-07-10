from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_project_api_start_script_uses_project_result_batch_publish_root() -> None:
    script = (ROOT / "project/scripts/start_project_api.ps1").read_text(encoding="utf-8")

    assert "data\\project_result_batches" in script
    assert "algo_main" not in script


def test_frontend_api_inventory_documents_project_result_batch_publish_root() -> None:
    inventory = (ROOT / "project/docs/frontend_api_inventory.md").read_text(encoding="utf-8")

    assert "data\\project_result_batches" in inventory
    assert "RISK_RESULT_BATCH_ROOT=C:\\Users\\admin\\Myprojects\\for_git\\algo_main" not in inventory
