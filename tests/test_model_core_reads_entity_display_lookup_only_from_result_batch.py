from __future__ import annotations

from pathlib import Path

import pandas as pd

from risk_model_core.manifest import RiskResultManifest
from risk_model_core.repositories import InMemoryRiskResultRepository
from risk_model_core.schemas import STANDARD_TABLES


def make_manifest() -> RiskResultManifest:
    return RiskResultManifest(
        batch_id="lookup-test",
        report_type="monthly",
        report_month="2025-12",
        report_date="2025-12-31",
        score_cutoff_month="2025-12-31",
        primary_horizon="H6",
        available_horizons=["H3", "H6", "H12"],
        schema_version="test",
        data_backend="in_memory",
        allowed_usage=["backend_api"],
        forbidden_usage=[],
        customer_facing_probability_service_allowed=False,
        auto_dispatch_allowed=False,
        proof_case_report_allowed=False,
        caveats=[],
        raw={},
    )


def test_model_core_loads_entity_display_lookup_from_result_batch_table() -> None:
    lookup = pd.DataFrame(
        [
            {
                "tenant_id": "tenant",
                "report_month": "2025-12",
                "manufacturer_code": "m1",
                "manufacturer_display_name": "m1",
                "hospital_code": "h1",
                "hospital_display_name": "Hospital One",
                "drug_code": "d1",
                "drug_group": "d1",
                "drug_display_name": "Drug One",
                "product_line_code": "pl1",
                "product_line_name": "Line One",
                "region_code": "r1",
                "region_display_name": "Region One",
                "display_key": "tenant|2025-12|m1|h1|d1",
                "display_name_source": "master",
                "display_name_quality": "master",
                "source_raw_batch_id": "raw",
                "updated_at": "2026-07-08T00:00:00+00:00",
            }
        ]
    )
    repo = InMemoryRiskResultRepository(make_manifest(), {"entity_display_lookup": lookup})

    loaded = repo.load_entity_display_lookup(report_month="2025-12", manufacturer_codes=["m1"])

    assert "entity_display_lookup" in STANDARD_TABLES
    assert loaded.iloc[0]["hospital_display_name"] == "Hospital One"
    assert loaded.iloc[0]["drug_display_name"] == "Drug One"


def test_model_core_source_has_no_algo_main_or_raw_mapping_dependency() -> None:
    root = Path(__file__).resolve().parents[1] / "risk_model_core"
    scanned = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    forbidden = ["algo_main", "bs_agent_dingdan_clean", "raw orders", "SQL_DATABASE_URL", "create_engine("]
    assert not [token for token in forbidden if token in scanned]
