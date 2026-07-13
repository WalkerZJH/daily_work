from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
import json

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from risk_model_core.manifest import RiskResultManifest
from risk_model_core.repositories import InMemoryRiskResultRepository


@contextmanager
def override_workbench_repository(repository: InMemoryRiskResultRepository | None = None) -> Iterator[None]:
    from app.api.routes_detector_results import get_detector_result_service
    from app.api.routes_frontend_pages import get_frontend_page_service
    from app.api.routes_report_context import get_report_context_service
    from app.api.routes_user_top_entities import get_user_top_entity_service
    from app.services.detector_result_service import DetectorResultService
    from app.services.frontend_page_service import FrontendPageService
    from app.services.report_context_service import ReportContextService
    from app.services.user_top_entity_service import TopEntityService, UserManufacturerScopeService

    repo = repository or _repository()
    scope_service = UserManufacturerScopeService.from_rows(_scope_rows())
    app.dependency_overrides[get_user_top_entity_service] = lambda: TopEntityService(
        repo,
        scope_service=scope_service,
    )
    app.dependency_overrides[get_detector_result_service] = lambda: DetectorResultService(repo)
    app.dependency_overrides[get_frontend_page_service] = lambda: FrontendPageService(
        repository=repo,
    )
    app.dependency_overrides[get_report_context_service] = lambda: ReportContextService(repo)
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_user_top_entity_service, None)
        app.dependency_overrides.pop(get_detector_result_service, None)
        app.dependency_overrides.pop(get_frontend_page_service, None)
        app.dependency_overrides.pop(get_report_context_service, None)


def test_workbench_intersects_manufacturer_scope_and_sorts_by_involved_amount() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/workbench",
            params=[
                ("manufacturer_code", "M1"),
                ("manufacturer_code", "M3"),
                ("horizon", "H3"),
                ("top_n", "1"),
                ("sort_by", "involved_amount"),
                ("run_date", "2026-07-08"),
            ],
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"]["manufacturer_codes"] == ["M1"]
    assert payload["query"]["horizon"] == "H3"
    assert payload["query"]["sort_by"] == "involved_amount"
    assert payload["rows"][0]["entity_id"] == "m1_entity"
    assert payload["rows"][0]["involved_amount"] == 100
    assert payload["rows"][0]["involved_amount_source"] == "purchase_amount_sum_last_3m_asof_cutoff"
    assert payload["detector_summary"]["latest_detector_run_date"] == "2026-07-08"
    assert payload["detector_summary"]["detector_clue_count"] == 1
    text = json.dumps(payload)
    assert payload["rows"][0]["loss_value"] == 20
    for forbidden in ["business_score", "fill_policy", "expected_loss", "model_metrics"]:
        assert forbidden not in text
    assert "M3" not in text


def test_workbench_sorts_by_horizon_risk_probability_across_visible_scope() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={"horizon": "H3", "top_n": 2, "sort_by": "risk_probability"},
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 200
    rows = response.json()["rows"]
    assert [row["entity_id"] for row in rows] == ["m2_entity", "m1_entity"]
    assert [row["risk_probability"] for row in rows] == [0.9, 0.2]
    assert all(row["horizon"] == "H3" for row in rows)


def test_workbench_h3_and_h12_use_distinct_horizon_profiles_for_ranking() -> None:
    with override_workbench_repository(_horizon_ranking_repository()):
        client = TestClient(app)
        h3_response = client.get(
            "/api/v1/workbench",
            params={"horizon": "H3", "top_n": 2, "sort_by": "risk_probability"},
            headers={"X-User-Id": "user_a"},
        )
        h12_response = client.get(
            "/api/v1/workbench",
            params={"horizon": "H12", "top_n": 2, "sort_by": "risk_probability"},
            headers={"X-User-Id": "user_a"},
        )

    assert h3_response.status_code == 200
    assert h12_response.status_code == 200
    h3_rows = h3_response.json()["rows"]
    h12_rows = h12_response.json()["rows"]
    assert [row["entity_id"] for row in h3_rows] == ["m1_entity", "m2_entity"]
    assert [row["risk_probability"] for row in h3_rows] == [0.9, 0.3]
    assert all(row["horizon"] == "H3" for row in h3_rows)
    assert [row["entity_id"] for row in h12_rows] == ["m2_entity", "m1_entity"]
    assert [row["risk_probability"] for row in h12_rows] == [0.95, 0.2]
    assert all(row["horizon"] == "H12" for row in h12_rows)


def test_workbench_filters_per_horizon_risk_entity_rows_before_profile_join() -> None:
    repo = _repository()
    repo.tables["risk_entities"] = pd.DataFrame(
        [
            _entity("same_entity|H3", "M1", "H3"),
            _entity("same_entity|H6", "M1", "H6"),
            _entity("same_entity|H12", "M1", "H12"),
        ]
    )
    repo.tables["risk_entity_horizon_profiles"] = pd.DataFrame(
        [
            _profile("same_entity|H3", "2026-07", "H3", 0.9, 100, "H3 profile"),
            _profile("same_entity|H3", "2026-07", "H6", 0.6, 200, "H6 profile"),
            _profile("same_entity|H3", "2026-07", "H12", 0.3, 300, "H12 profile"),
            _profile("same_entity|H6", "2026-07", "H3", 0.9, 100, "H3 profile"),
            _profile("same_entity|H6", "2026-07", "H6", 0.6, 200, "H6 profile"),
            _profile("same_entity|H6", "2026-07", "H12", 0.3, 300, "H12 profile"),
            _profile("same_entity|H12", "2026-07", "H3", 0.9, 100, "H3 profile"),
            _profile("same_entity|H12", "2026-07", "H6", 0.6, 200, "H6 profile"),
            _profile("same_entity|H12", "2026-07", "H12", 0.3, 300, "H12 profile"),
        ]
    )

    with override_workbench_repository(repo):
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={"manufacturer_code": "M1", "horizon": "H3", "top_n": 10, "sort_by": "risk_probability"},
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 200
    rows = response.json()["rows"]
    assert [row["entity_id"] for row in rows] == ["same_entity|H3"]
    assert rows[0]["horizon"] == "H3"
    assert rows[0]["risk_probability"] == 0.9


def test_workbench_unavailable_horizon_returns_422_without_primary_horizon_fallback() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={"manufacturer_code": "M1", "horizon": "H24", "top_n": 10, "sort_by": "risk_probability"},
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "error_code": "HORIZON_NOT_AVAILABLE",
        "requested_horizon": "H24",
        "available_horizons": ["H3", "H6", "H12"],
    }


def test_workbench_horizon_profiles_override_base_probability_and_amount_columns() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={
                "manufacturer_code": "M1",
                "horizon": "H6",
                "top_n": 1,
                "sort_by": "loss_value",
            },
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 200
    row = response.json()["rows"][0]
    assert row["entity_id"] == "m1_entity"
    assert row["horizon"] == "H6"
    assert row["risk_probability"] == 0.7
    assert row["involved_amount"] == 200
    assert row["loss_value"] == 140


def test_current_user_manufacturer_options_are_backend_scoped() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/my/manufacturers",
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["manufacturer_count"] == 2
    assert payload["manufacturers"] == [
        {"manufacturer_code": "M1", "manufacturer_display_name": "Manufacturer One", "manufacturer_name": "Manufacturer One"},
        {"manufacturer_code": "M2", "manufacturer_display_name": "Manufacturer Two", "manufacturer_name": "Manufacturer Two"},
    ]
    assert payload["items"] == [
        {"manufacturer_code": "M1", "manufacturer_display_name": "Manufacturer One", "manufacturer_name": "Manufacturer One"},
        {"manufacturer_code": "M2", "manufacturer_display_name": "Manufacturer Two", "manufacturer_name": "Manufacturer Two"},
    ]


def test_manufacturer_catalog_ignores_current_selected_manufacturer_query() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/my/manufacturers",
            params={"manufacturer_code": "M1", "horizon": "H3", "run_date": "2026-07-08"},
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["manufacturer_count"] == 2
    assert [item["manufacturer_code"] for item in payload["manufacturers"]] == ["M1", "M2"]


def test_workbench_single_manufacturer_scope_never_returns_other_manufacturers() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={"manufacturer_code": "M1", "horizon": "H3", "top_n": 10, "sort_by": "risk_probability"},
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"]["scope_applied"] is True
    assert payload["scope"]["requested_manufacturer_code"] == "M1"
    assert {row["manufacturer_code"] for row in payload["rows"]} == {"M1"}
    assert payload["detector_summary"]["detector_clue_count"] == 1


def test_workbench_detector_summary_uses_scoped_total_not_first_page_size() -> None:
    repo = _repository()
    base = repo.tables["daily_detector_clues"].iloc[0].to_dict()
    repo.tables["daily_detector_clues"] = pd.DataFrame(
        [
            {
                **base,
                "detector_clue_id": f"m1_clue_{index}",
                "display_rank": index + 1,
            }
            for index in range(205)
        ]
    )
    with override_workbench_repository(repo):
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={"manufacturer_code": "M1", "horizon": "H3", "top_n": 10, "sort_by": "risk_probability"},
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 200
    assert response.json()["detector_summary"]["detector_clue_count"] == 205


def test_workbench_forbidden_manufacturer_returns_403_without_global_fallback() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={"manufacturer_code": "M3", "horizon": "H3", "top_n": 10, "sort_by": "risk_probability"},
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == "MANUFACTURER_SCOPE_FORBIDDEN"


def test_workbench_empty_selected_scope_returns_scoped_empty_without_global_fallback() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={"manufacturer_code": "M2", "horizon": "H12", "top_n": 10, "sort_by": "risk_probability"},
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"] == []
    assert payload["scope"]["scope_applied"] is True
    assert payload["scope"]["requested_manufacturer_code"] == "M2"
    assert payload["scope"]["row_count"] == 0
    assert payload["empty_reason"] == "NO_RISK_ENTITIES_IN_SELECTED_SCOPE"


def test_workbench_loss_value_sort_orders_positive_zero_then_missing_amount() -> None:
    with override_workbench_repository(_loss_sort_repository()):
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={"manufacturer_code": "M1", "horizon": "H6", "top_n": 10, "sort_by": "loss_value"},
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 200
    rows = response.json()["rows"]
    assert [row["entity_id"] for row in rows] == ["loss_c", "loss_a", "loss_d", "loss_b"]
    assert [row["loss_value"] for row in rows] == [400, 90, 0, None]
    assert [row["involved_amount"] for row in rows] == [1000, 100, 0, None]


def test_workbench_loss_value_sort_unavailable_when_all_amounts_missing() -> None:
    repo = _loss_sort_repository()
    repo.tables["risk_entity_horizon_profiles"]["involved_amount"] = None
    with override_workbench_repository(repo):
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={"manufacturer_code": "M1", "horizon": "H6", "top_n": 10, "sort_by": "loss_value"},
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "error_code": "SORT_METRIC_NOT_AVAILABLE",
        "requested_sort_by": "loss_value",
    }


def test_workbench_detector_score_sort_unavailable_without_metric() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={"manufacturer_code": "M1", "horizon": "H3", "top_n": 10, "sort_by": "detector_score"},
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "error_code": "SORT_METRIC_NOT_AVAILABLE",
        "requested_sort_by": "detector_score",
    }


def test_daily_detector_dates_return_run_status_without_daily_probability_claim() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/daily-detector/dates",
            params={"report_month": "2026-07"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["run_date"] == "2026-07-08"
    assert payload["items"][0]["status"] == "ready"
    assert "monthly model probabilities do not change daily" in " ".join(payload["semantic_caveats"])


def test_risk_entity_detail_uses_requested_horizon_profile() -> None:
    with override_workbench_repository():
        response = TestClient(app).get("/api/v1/risk-entities/m1_entity", params={"horizon": "H3"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_horizon"] == "H3"
    assert payload["entity"]["horizon"] == "H3"
    assert payload["entity"]["risk_probability"] == 0.2
    assert payload["entity"]["involved_amount"] == 100
    assert payload["entity"]["candidate_type"] == "recurring"
    assert payload["entity"]["manufacturer_display_name"] == "Manufacturer One"
    assert payload["entity"]["manufacturer_name"] == "Manufacturer One"
    assert payload["selected_horizon_profile"]["reason"] == "M1 H3 reason"
    assert "business_score" not in json.dumps(payload)


def test_probability_trend_returns_selected_horizon_profiles_by_report_month() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/risk-entities/m1_entity/probability-trend",
            params={"horizon": "H3"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_entity_id"] == "m1_entity"
    assert payload["horizon"] == "H3"
    assert [item["report_month"] for item in payload["items"]] == ["2026-06", "2026-07"]
    assert [item["involved_amount"] for item in payload["items"]] == [80, 100]
    assert "loss_value" not in json.dumps(payload)


def test_detector_evidence_supports_run_date_family_and_detector_filters() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/risk-entities/m1_entity/detector-evidence",
            params={
                "run_date": "2026-07-08",
                "detector_family": "purchase_interval",
                "detector_id": "purchase_interval_ipi",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["detector_id"] for item in payload["items"]] == ["purchase_interval_ipi"]
    assert payload["items"][0]["run_date"] == "2026-07-08"
    assert "detector_probability" not in json.dumps(payload)


def test_detector_evidence_rejects_entity_outside_requested_manufacturer() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/risk-entities/m2_entity/detector-evidence",
            params={"run_date": "2026-07-08", "manufacturer_code": "M1"},
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == "MANUFACTURER_SCOPE_FORBIDDEN"


def test_daily_detector_status_is_scoped_to_requested_manufacturer() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/daily-detector/status",
            params={"run_date": "2026-07-08", "manufacturer_code": "M1"},
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["clue_count"] == 1
    assert payload["highest_detector_score"] == 0.82


def test_risk_entity_detail_rejects_entity_outside_requested_manufacturer() -> None:
    with override_workbench_repository():
        response = TestClient(app).get(
            "/api/v1/risk-entities/m2_entity",
            params={"manufacturer_code": "M1", "horizon": "H3"},
            headers={"X-User-Id": "user_a"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == "MANUFACTURER_SCOPE_FORBIDDEN"


def _repository() -> InMemoryRiskResultRepository:
    return InMemoryRiskResultRepository(
        _manifest(),
        {
            "risk_entities": _risk_entities(),
            "risk_entity_horizon_profiles": _horizon_profiles(),
            "entity_display_lookup": _display_lookup(),
            "detector_catalog": _detector_catalog(),
            "daily_detector_runs": _daily_detector_runs(),
            "daily_detector_clues": _daily_detector_clues(),
            "high_risk_detector_evidence": _high_risk_detector_evidence(),
            "risk_cards": pd.DataFrame(),
            "risk_card_evidence": pd.DataFrame(),
            "risk_entity_timeline": pd.DataFrame(),
            "monthly_reports": pd.DataFrame(),
            "proof_cases": pd.DataFrame(),
        },
    )


def _loss_sort_repository() -> InMemoryRiskResultRepository:
    repo = _repository()
    repo.tables["risk_entities"] = pd.DataFrame(
        [
            _entity("loss_a", "M1", "H6"),
            _entity("loss_b", "M1", "H6"),
            _entity("loss_c", "M1", "H6"),
            _entity("loss_d", "M1", "H6"),
        ]
    )
    repo.tables["risk_entity_horizon_profiles"] = pd.DataFrame(
        [
            _profile("loss_a", "2026-07", "H6", 0.9, 100, "loss A"),
            _profile("loss_b", "2026-07", "H6", 0.8, None, "loss B"),
            _profile("loss_c", "2026-07", "H6", 0.4, 1000, "loss C"),
            _profile("loss_d", "2026-07", "H6", 0.95, 0, "loss D"),
        ]
    )
    repo.tables["entity_display_lookup"] = pd.DataFrame(
        [
            {
                "tenant_id": "tenant",
                "report_month": "2026-07",
                "manufacturer_code": "M1",
                "manufacturer_display_name": "Manufacturer One",
                "hospital_code": f"{entity_id}_hospital",
                "hospital_display_name": f"{entity_id} hospital display",
                "drug_code": f"{entity_id}_drug",
                "drug_group": f"{entity_id}_drug",
                "drug_display_name": f"{entity_id} drug display",
                "product_line_code": "",
                "product_line_name": "",
                "region_code": "",
                "region_display_name": "region display",
                "display_key": entity_id,
                "display_name_source": "fixture",
                "display_name_quality": "master",
                "source_raw_batch_id": "raw",
                "updated_at": "2026-07-31T00:00:00+00:00",
            }
            for entity_id in ["loss_a", "loss_b", "loss_c", "loss_d"]
        ]
    )
    return repo


def _horizon_ranking_repository() -> InMemoryRiskResultRepository:
    repo = _repository()
    repo.tables["risk_entity_horizon_profiles"] = pd.DataFrame(
        [
            _profile("m1_entity", "2026-07", "H3", 0.9, 100, "M1 H3 high"),
            _profile("m2_entity", "2026-07", "H3", 0.3, 200, "M2 H3 low"),
            _profile("m1_entity", "2026-07", "H6", 0.5, 100, "M1 H6"),
            _profile("m2_entity", "2026-07", "H6", 0.6, 200, "M2 H6"),
            _profile("m1_entity", "2026-07", "H12", 0.2, 100, "M1 H12 low"),
            _profile("m2_entity", "2026-07", "H12", 0.95, 200, "M2 H12 high"),
        ]
    )
    return repo


def _manifest() -> RiskResultManifest:
    return RiskResultManifest(
        batch_id="project-workbench-test",
        report_type="monthly",
        report_month="2026-07",
        report_date="2026-07-31",
        score_cutoff_month="2026-07-31",
        primary_horizon="H6",
        available_horizons=["H3", "H6", "H12"],
        schema_version="risk_result_batch_monthly_v2",
        data_backend="memory",
        allowed_usage=["backend_api"],
        forbidden_usage=[],
        customer_facing_probability_service_allowed=False,
        auto_dispatch_allowed=False,
        proof_case_report_allowed=False,
        caveats=[],
        raw={
            "batch_id": "project-workbench-test",
            "result_batch_id": "project-workbench-test",
            "report_type": "monthly",
            "report_month": "2026-07",
            "report_date": "2026-07-31",
            "score_as_of_date": "2026-07-31",
            "run_date": "2026-07-08",
            "available_horizons": ["H3", "H6", "H12"],
            "primary_horizon": "H6",
            "detector_config_version": "daily_detector_rules_v1",
            "conditional_fact_mode_ready": True,
            "caveats": ["detector_score is not probability"],
        },
    )


def _risk_entities() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _entity("m1_entity", "M1", "H6"),
            _entity("m2_entity", "M2", "H6"),
            _entity("m3_entity", "M3", "H6"),
        ]
    )


def _entity(entity_id: str, manufacturer_code: str, horizon: str) -> dict[str, object]:
    return {
        "risk_entity_id": entity_id,
        "candidate_id": entity_id + "|" + horizon,
        "tenant_id": "tenant",
        "manufacturer_code": manufacturer_code,
        "hospital_code": entity_id + "_hospital",
        "hospital_display_name": entity_id + " hospital",
        "drug_group": entity_id + "_drug",
        "drug_display_name": entity_id + " drug",
        "region_display_name": "region",
        "report_month": "2026-07",
        "primary_horizon": horizon,
        "risk_probability": 0.01,
        "risk_probability_value": 0.5,
        "involved_amount": 1,
        "risk_level": "orange",
        "risk_color": "orange",
        "review_status": "recurring",
        "final_candidate_status": "priority_review",
        "candidate_type": "recurring",
        "auto_dispatch_allowed": False,
        "is_high_risk": True,
        "is_observation": False,
        "is_one_shot": False,
        "main_reason_summary": "monthly reason",
    }


def _horizon_profiles() -> pd.DataFrame:
    rows = [
        _profile("m1_entity", "2026-06", "H3", 0.1, 80, "M1 H3 previous"),
        _profile("m1_entity", "2026-07", "H3", 0.2, 100, "M1 H3 reason"),
        _profile("m1_entity", "2026-07", "H6", 0.7, 200, "M1 H6 reason"),
        _profile("m1_entity", "2026-07", "H12", 0.4, 300, "M1 H12 reason"),
        _profile("m2_entity", "2026-07", "H3", 0.9, 90, "M2 H3 reason"),
        _profile("m2_entity", "2026-07", "H6", 0.3, 400, "M2 H6 reason"),
        _profile("m3_entity", "2026-07", "H3", 0.99, 999, "M3 forbidden"),
    ]
    return pd.DataFrame(rows)


def _profile(
    entity_id: str,
    report_month: str,
    horizon: str,
    probability: float,
    amount: int | None,
    reason: str,
) -> dict[str, object]:
    months = horizon.replace("H", "")
    return {
        "risk_entity_id": entity_id,
        "report_month": report_month,
        "horizon": horizon,
        "risk_probability": probability,
        "involved_amount": amount,
        "involved_amount_source": f"purchase_amount_sum_last_{months}m_asof_cutoff",
        "risk_level": "orange",
        "risk_band": "Medium risk",
        "main_reason_summary": reason,
        "reason": reason,
        "detector_evidence_count": 1,
        "updated_at": "2026-07-31T00:00:00+00:00",
    }


def _display_lookup() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "tenant_id": "tenant",
                "report_month": "2026-07",
                "manufacturer_code": code,
                "manufacturer_display_name": name,
                "hospital_code": f"{entity_id}_hospital",
                "hospital_display_name": f"{entity_id} hospital display",
                "drug_code": f"{entity_id}_drug",
                "drug_group": f"{entity_id}_drug",
                "drug_display_name": f"{entity_id} drug display",
                "product_line_code": "",
                "product_line_name": "",
                "region_code": "",
                "region_display_name": "region display",
                "display_key": entity_id,
                "display_name_source": "fixture",
                "display_name_quality": "master",
                "source_raw_batch_id": "raw",
                "updated_at": "2026-07-31T00:00:00+00:00",
            }
            for code, name, entity_id in [
                ("M1", "Manufacturer One", "m1_entity"),
                ("M2", "Manufacturer Two", "m2_entity"),
                ("M3", "Manufacturer Three", "m3_entity"),
            ]
        ]
    )


def _detector_catalog() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "detector_id": "purchase_interval_ipi",
                "detector_family": "purchase_interval",
                "detector_name": "Purchase Interval IPI",
                "status": "implemented",
                "enabled_by_default": True,
                "method": "rule_result_batch",
                "required_fields": "[]",
                "optional_fields": "[]",
                "output_schema_version": "daily_detector_clue_v1",
                "caveat": "",
            },
            {
                "detector_id": "purchase_frequency_drop",
                "detector_family": "purchase_frequency",
                "detector_name": "Purchase Frequency Drop",
                "status": "implemented",
                "enabled_by_default": True,
                "method": "rule_result_batch",
                "required_fields": "[]",
                "optional_fields": "[]",
                "output_schema_version": "daily_detector_clue_v1",
                "caveat": "",
            },
        ]
    )


def _daily_detector_runs() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "detector_run_id": "run_2026_07_08",
                "run_date": "2026-07-08",
                "report_month": "2026-07",
                "source_result_batch_id": "project-workbench-test",
                "detector_config_version": "daily_detector_rules_v1",
                "enabled_detectors": "purchase_interval_ipi,purchase_frequency_drop",
                "scanned_entity_count": 3,
                "clue_count": 2,
                "attached_high_risk_count": 1,
                "created_at": "2026-07-08T09:00:00+08:00",
            }
        ]
    )


def _daily_detector_clues() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "detector_clue_id": "m1_clue",
                "detector_run_id": "run_2026_07_08",
                "run_date": "2026-07-08",
                "tenant_id": "tenant",
                "manufacturer_code": "M1",
                "hospital_code": "m1_entity_hospital",
                "drug_group": "m1_entity_drug",
                "detector_id": "purchase_interval_ipi",
                "detector_family": "purchase_interval",
                "detector_score": 0.82,
                "detector_level": "warning",
                "confidence": 0.7,
                "hit_flag": True,
                "root_cause_label": "规则证据命中",
                "evidence_text": "建议复核采购节奏",
                "evidence_payload": "{}",
                "is_monthly_high_risk_entity": True,
                "risk_entity_id": "m1_entity",
                "monthly_risk_probability": 0.7,
                "monthly_loss_value": 200,
                "display_rank": 1,
                "caveat": "detector_score is rule inspection score, not probability",
                "created_at": "2026-07-08T09:05:00+08:00",
            },
            {
                "detector_clue_id": "m2_clue",
                "detector_run_id": "run_2026_07_08",
                "run_date": "2026-07-08",
                "tenant_id": "tenant",
                "manufacturer_code": "M2",
                "hospital_code": "m2_entity_hospital",
                "drug_group": "m2_entity_drug",
                "detector_id": "purchase_frequency_drop",
                "detector_family": "purchase_frequency",
                "detector_score": 0.76,
                "detector_level": "watch",
                "confidence": 0.6,
                "hit_flag": True,
                "root_cause_label": "规则证据命中",
                "evidence_text": "建议复核采购节奏",
                "evidence_payload": "{}",
                "is_monthly_high_risk_entity": True,
                "risk_entity_id": "m2_entity",
                "monthly_risk_probability": 0.3,
                "monthly_loss_value": 400,
                "display_rank": 2,
                "caveat": "detector_score is rule inspection score, not probability",
                "created_at": "2026-07-08T09:06:00+08:00",
            },
        ]
    )


def _high_risk_detector_evidence() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "risk_entity_id": "m1_entity",
                "detector_run_id": "run_2026_07_08",
                "run_date": "2026-07-08",
                "detector_id": "purchase_interval_ipi",
                "detector_family": "purchase_interval",
                "detector_score": 0.82,
                "confidence": 0.7,
                "root_cause_label": "规则证据命中",
                "evidence_text": "建议复核采购节奏",
                "evidence_payload": "{}",
                "caveat": "detector_score is rule inspection score, not probability",
                "created_at": "2026-07-08T09:05:00+08:00",
            },
            {
                "risk_entity_id": "m1_entity",
                "detector_run_id": "run_2026_07_08",
                "run_date": "2026-07-08",
                "detector_id": "purchase_frequency_drop",
                "detector_family": "purchase_frequency",
                "detector_score": 0.76,
                "confidence": 0.6,
                "root_cause_label": "规则证据命中",
                "evidence_text": "建议复核采购节奏",
                "evidence_payload": "{}",
                "caveat": "detector_score is rule inspection score, not probability",
                "created_at": "2026-07-08T09:06:00+08:00",
            },
        ]
    )


def _scope_rows() -> list[dict[str, object]]:
    return [
        {
            "user_id": "user_a",
            "manufacturer_code": "M1",
            "manufacturer_display_name": "Manufacturer One",
            "enabled": True,
        },
        {
            "user_id": "user_a",
            "manufacturer_code": "M2",
            "manufacturer_display_name": "Manufacturer Two",
            "enabled": True,
        },
    ]
