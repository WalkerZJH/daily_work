from __future__ import annotations

from contextlib import contextmanager
import json

from fastapi.testclient import TestClient
import pandas as pd

from app.main import app
from app.services.detector_result_service import DetectorResultService
from app.services.report_context_service import ReportContextService
from project.tests.detector_result_test_utils import make_detector_repository
from risk_algorithm_core.detector_catalog import build_detector_catalog
from risk_model_core.repositories import CompositeDetectorResultRepository


@contextmanager
def _override_entity_detail_dependencies(repository):
    from app.api.routes_detector_results import get_detector_result_service
    from app.api.routes_report_context import get_report_context_service

    app.dependency_overrides[get_detector_result_service] = lambda: DetectorResultService(repository)
    app.dependency_overrides[get_report_context_service] = lambda: ReportContextService(repository)
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_detector_result_service, None)
        app.dependency_overrides.pop(get_report_context_service, None)


def _release_b_repository():
    repository = make_detector_repository()
    second = repository.tables["daily_detector_results"].iloc[[0]].copy()
    second.loc[:, "detector_result_id"] = "clue_high_frequency"
    second.loc[:, "detector_id"] = "purchase_frequency_drop"
    second.loc[:, "detector_family"] = "purchase_frequency"
    second.loc[:, "detector_name"] = "Purchase frequency drop"
    repository.tables["daily_detector_results"] = pd.concat(
        [repository.tables["daily_detector_results"], second], ignore_index=True
    )
    repository.tables["entity_display_lookup"] = pd.DataFrame(
        [
            {
                "tenant_id": "tenant",
                "report_month": "2025-12",
                "manufacturer_code": "m1",
                "manufacturer_display_name": "生产企业一",
                "hospital_code": "h1",
                "hospital_display_name": "医院一",
                "drug_code": "d1",
                "drug_display_name": "药品一",
            }
        ]
    )
    repository.tables["risk_entity_horizon_profiles"] = pd.DataFrame(
        [
            {
                "risk_entity_id": "entity_high",
                "report_month": "2025-12",
                "horizon": "H6",
                "risk_probability": 0.91,
                "involved_amount": 910,
            }
        ]
    )
    return repository


def test_entity_detail_returns_all_exact_daily_hits_and_optional_monthly_context() -> None:
    repository = _release_b_repository()
    payload = DetectorResultService(repository).entity_detail(
        observation_date="2025-12-31",
        manufacturer_code="m1",
        hospital_code="h1",
        drug_code="d1",
        clue_id="clue_high",
        probability_repository=repository,
        horizon="H6",
    )

    assert payload["detector_hit_count"] == 2
    assert {item["detector_id"] for item in payload["detector_hits"]} == {
        "purchase_interval_ipi",
        "purchase_frequency_drop",
    }
    assert payload["entity"]["hospital_name"] == "医院一"
    assert payload["entity"]["drug_name"] == "药品一"
    assert payload["monthly_prediction"]["risk_entity_id"] == "entity_high"
    assert payload["monthly_prediction"]["risk_probability"] == 0.91


def test_entity_detail_keeps_detector_only_entity_and_exact_date_scope() -> None:
    repository = _release_b_repository()
    service = DetectorResultService(repository)
    detector_only = service.entity_detail(
        observation_date="2025-12-31",
        manufacturer_code="m1",
        hospital_code="h2",
        drug_code="d2",
        probability_repository=repository,
    )
    other_date = service.entity_detail(
        observation_date="2025-12-30",
        manufacturer_code="m1",
        hospital_code="h2",
        drug_code="d2",
        probability_repository=repository,
    )

    assert detector_only["detector_hit_count"] == 1
    assert detector_only["entity"]["hospital_name"] == "h2"
    assert detector_only["entity"]["drug_name"] == "d2"
    assert detector_only["monthly_prediction"] is None
    assert "MONTHLY_ENTITY_NOT_FOUND" in detector_only["warnings"]
    assert other_date["detector_hit_count"] == 0


def test_entity_detail_api_accepts_full_entity_key() -> None:
    repository = _release_b_repository()
    with _override_entity_detail_dependencies(repository):
        response = TestClient(app).get(
            "/api/v1/detectors/entity-detail",
            params={
                "observation_date": "2025-12-31",
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_code": "d1",
                "clue_id": "clue_high",
                "horizon": "H6",
            },
        )

    assert response.status_code == 200
    assert response.json()["detector_hit_count"] == 2
    assert response.json()["entity"]["manufacturer_code"] == "m1"


def test_composite_repository_delegates_display_lookup_to_exact_associated_repository(tmp_path) -> None:
    component = tmp_path / "detector_id=purchase_interval_ipi" / "batch_id=test"
    component.mkdir(parents=True)
    (component / "manifest.json").write_text(
        json.dumps(
            {
                "batch_id": "test",
                "report_type": "daily_detector_component",
                "schema_version": "test",
                "data_backend": "parquet",
                "observation_date": "2025-12-31",
                "detector_run_date": "2025-12-31",
                "detector_tables": [],
                "caveats": [],
            }
        ),
        encoding="utf-8",
    )
    display_repository = _release_b_repository()

    repository = CompositeDetectorResultRepository(
        tmp_path,
        display_lookup_repository=display_repository,
    )
    lookup = repository.load_entity_display_lookup(manufacturer_code="m1", hospital_code="h1")

    assert lookup.iloc[0]["hospital_display_name"] == "医院一"
    assert lookup.iloc[0]["drug_code"] == "d1"


def test_implemented_catalog_has_stable_release_b_chinese_fields() -> None:
    catalog = build_detector_catalog()
    implemented = catalog.loc[catalog["status"].eq("implemented")]

    assert len(implemented) == 10
    assert implemented["detector_name_zh"].str.strip().ne("").all()
    assert implemented["detector_name_en"].str.strip().ne("").all()
    assert implemented["detector_description_zh"].str.strip().ne("").all()
    assert implemented["detector_family_name_zh"].str.strip().ne("").all()
    quantity = implemented.loc[implemented["detector_id"].eq("purchase_quantity_trend")].iloc[0]
    assert "简单比例规则 v1" in quantity["detector_description_zh"]


def test_stable_sample_names_and_leading_zero_codes_are_preserved() -> None:
    repository = _release_b_repository()
    manufacturer_code = "DFC52FC0D392458D9BC44C3CD2C739DC"
    hospital_code = "YL221606"
    drug_code = "ZA12AAN0014010203711"
    hit_mask = repository.tables["daily_detector_results"]["hospital_code"].eq("h1")
    repository.tables["daily_detector_results"].loc[hit_mask, ["manufacturer_code", "hospital_code", "drug_code"]] = [
        manufacturer_code,
        hospital_code,
        drug_code,
    ]
    repository.tables["risk_entities"].loc[:, ["manufacturer_code", "hospital_code", "drug_group"]] = [
        manufacturer_code,
        hospital_code,
        drug_code,
    ]
    repository.tables["entity_display_lookup"] = pd.DataFrame(
        [
            {
                "tenant_id": "tenant",
                "report_month": "2025-12",
                "manufacturer_code": manufacturer_code,
                "manufacturer_display_name": "哈药集团制药六厂",
                "hospital_code": hospital_code,
                "hospital_display_name": "吉林省前卫医院",
                "drug_code": drug_code,
                "drug_display_name": "脑安片",
            }
        ]
    )

    payload = DetectorResultService(repository).entity_detail(
        observation_date="2025-12-31",
        manufacturer_code=manufacturer_code,
        hospital_code=hospital_code,
        drug_code=drug_code,
        probability_repository=repository,
    )

    assert payload["entity"]["manufacturer_name"] == "哈药集团制药六厂"
    assert payload["entity"]["hospital_name"] == "吉林省前卫医院"
    assert payload["entity"]["drug_name"] == "脑安片"
    assert payload["entity"]["drug_code"] == drug_code

    detector_only = repository.tables["daily_detector_results"]["hospital_code"].eq("h2")
    repository.tables["daily_detector_results"].loc[detector_only, "drug_code"] = "00123"
    leading_zero = DetectorResultService(repository).entity_detail(
        observation_date="2025-12-31",
        manufacturer_code="m1",
        hospital_code="h2",
        drug_code="00123",
    )
    assert leading_zero["entity"]["drug_code"] == "00123"
    assert leading_zero["detector_hit_count"] == 1


def test_openapi_discovers_release_b_list_detail_evidence_and_trend_routes() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/daily-detector/clues" in paths
    assert "/api/v1/detectors/entity-detail" in paths
    assert "/api/v1/risk-entities/{risk_entity_id}/detector-evidence" in paths
    assert "/api/v1/risk-entities/{entity_id}/probability-trend" in paths


def test_entity_detail_manufacturer_key_does_not_leak_another_manufacturer_hits() -> None:
    repository = _release_b_repository()
    with _override_entity_detail_dependencies(repository):
        response = TestClient(app).get(
            "/api/v1/detectors/entity-detail",
            params={
                "observation_date": "2025-12-31",
                "manufacturer_code": "another-manufacturer",
                "hospital_code": "h1",
                "drug_code": "d1",
            },
        )

    assert response.status_code == 200
    assert response.json()["detector_hit_count"] == 0
    assert response.json()["monthly_prediction"] is None
