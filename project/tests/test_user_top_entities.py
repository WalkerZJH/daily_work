from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from risk_model_core.manifest import RiskResultManifest
from risk_model_core.repositories import InMemoryRiskResultRepository


def test_user_top_entities_default_merges_visible_scope_before_taking_top_n() -> None:
    from app.services.user_top_entity_service import TopEntityService, UserManufacturerScopeService

    payload = TopEntityService(
        _repository(),
        scope_service=UserManufacturerScopeService.from_rows(_scope_rows()),
    ).list_user_top_entities(
        user_id="user_a",
        top_n=2,
        ranking_strategy="probability",
    )

    assert payload["group_by"] == "user_scope"
    assert payload["scope_mode"] == "user_scope"
    assert payload["scope"]["manufacturer_codes"] == ["M1", "M2"]
    assert len(payload["groups"]) == 1
    assert payload["groups"][0]["manufacturer_code"] == "user_scope"
    assert payload["groups"][0]["returned_count"] == 2
    assert [item["risk_entity_id"] for item in payload["groups"][0]["entities"]] == [
        "m1_high",
        "m2_high",
    ]
    assert "m1_second_threshold" not in json.dumps(payload)
    assert "M3" not in json.dumps(payload)


def test_group_by_manufacturer_is_retained_as_deprecated_internal_mode() -> None:
    from app.services.user_top_entity_service import TopEntityService, UserManufacturerScopeService

    payload = TopEntityService(
        _repository(),
        scope_service=UserManufacturerScopeService.from_rows(_scope_rows()),
    ).list_user_top_entities(
        user_id="user_a",
        top_n=1,
        group_by="manufacturer",
        ranking_strategy="probability",
    )

    assert payload["scope"]["manufacturer_codes"] == ["M1", "M2"]
    assert [group["manufacturer_code"] for group in payload["groups"]] == ["M1", "M2"]
    assert payload["groups"][0]["entities"][0]["risk_entity_id"] == "m1_high"
    assert payload["groups"][1]["entities"][0]["risk_entity_id"] == "m2_high"
    assert "GROUP_BY_MANUFACTURER_DEPRECATED_INTERNAL_ONLY" in payload["warnings"]
    assert "M3" not in json.dumps(payload)


def test_user_top_entities_requested_manufacturers_are_intersected_with_scope() -> None:
    from app.services.user_top_entity_service import TopEntityService, UserManufacturerScopeService

    payload = TopEntityService(
        _repository(),
        scope_service=UserManufacturerScopeService.from_rows(_scope_rows()),
    ).list_user_top_entities(
        user_id="user_a",
        manufacturer_codes=["M1", "M3"],
        top_n=5,
        ranking_strategy="probability",
    )

    assert payload["scope"]["manufacturer_codes"] == ["M1"]
    assert payload["group_by"] == "user_scope"
    assert [group["manufacturer_code"] for group in payload["groups"]] == ["user_scope"]
    assert all(entity["manufacturer_code"] == "M1" for entity in payload["groups"][0]["entities"])


def test_user_scope_group_takes_top_n_after_combining_visible_manufacturers() -> None:
    from app.services.user_top_entity_service import TopEntityService, UserManufacturerScopeService

    payload = TopEntityService(
        _repository(),
        scope_service=UserManufacturerScopeService.from_rows(_scope_rows()),
    ).list_user_top_entities(
        user_id="user_a",
        top_n=2,
        group_by="user_scope",
        ranking_strategy="probability",
    )

    assert len(payload["groups"]) == 1
    assert payload["groups"][0]["manufacturer_code"] == "user_scope"
    assert payload["groups"][0]["returned_count"] == 2
    assert [item["risk_entity_id"] for item in payload["groups"][0]["entities"]] == [
        "m1_high",
        "m2_high",
    ]


def test_mixed_strategy_downgrades_to_probability_when_batch_lacks_rank_fields() -> None:
    from app.services.user_top_entity_service import TopEntityService, UserManufacturerScopeService

    payload = TopEntityService(
        _repository(),
        scope_service=UserManufacturerScopeService.from_rows(_scope_rows()),
    ).list_user_top_entities(
        user_id="user_a",
        top_n=2,
        ranking_strategy="mixed_v2",
    )

    assert payload["ranking_strategy"] == "mixed_v2"
    assert payload["effective_ranking_strategy"] == "probability"
    assert payload["ranking_strategy_effective"] == "probability"
    assert "missing_mixed_fields" in payload["ranking_strategy_warning"]
    assert any("MIXED_V2_DOWNGRADED_TO_PROBABILITY" in warning for warning in payload["warnings"])
    assert any("missing_mixed_fields" in warning for warning in payload["warnings"])
    assert payload["groups"][0]["entities"][0]["ranking_score_source"] == "risk_probability_value"


def test_probability_threshold_overflow_policy_is_explicit() -> None:
    from app.services.user_top_entity_service import TopEntityService, UserManufacturerScopeService

    service = TopEntityService(
        _repository(),
        scope_service=UserManufacturerScopeService.from_rows(_scope_rows()),
    )

    capped = service.list_user_top_entities(
        user_id="user_a",
        top_n=1,
        ranking_strategy="probability",
        probability_threshold=0.8,
        include_threshold_overflow=False,
    )
    overflow = service.list_user_top_entities(
        user_id="user_a",
        top_n=1,
        ranking_strategy="probability",
        probability_threshold=0.8,
        include_threshold_overflow=True,
    )

    scoped_capped = capped["groups"][0]
    scoped_overflow = overflow["groups"][0]
    assert scoped_capped["threshold_hit_count"] == 3
    assert scoped_capped["returned_count"] == 1
    assert scoped_capped["overflow_count"] == 0
    assert scoped_overflow["threshold_hit_count"] == 3
    assert scoped_overflow["returned_count"] == 3
    assert scoped_overflow["overflow_count"] == 2
    assert "THRESHOLD_OVERFLOW_DEPRECATED_INTERNAL_ONLY" in overflow["warnings"]


def test_fill_policy_does_not_turn_observation_or_oneshot_into_high_risk() -> None:
    from app.services.user_top_entity_service import TopEntityService, UserManufacturerScopeService

    service = TopEntityService(
        _repository(),
        scope_service=UserManufacturerScopeService.from_rows(_scope_rows()),
    )

    observation_fill = service.list_user_top_entities(
        user_id="user_b",
        manufacturer_codes=["M4"],
        top_n=2,
        fill_policy="observation_fill",
    )
    oneshot_fill = service.list_user_top_entities(
        user_id="user_b",
        manufacturer_codes=["M5"],
        top_n=2,
        fill_policy="one_shot_fill",
    )

    observation = observation_fill["groups"][0]["entities"][1]
    oneshot = oneshot_fill["groups"][0]["entities"][1]
    assert observation["candidate_type"] == "observation"
    assert observation["is_high_risk"] is False
    assert "FILL_POLICY_DEPRECATED_INTERNAL_ONLY" in observation_fill["warnings"]
    assert oneshot["candidate_type"] == "one_shot"
    assert oneshot["is_high_risk"] is False
    assert oneshot["risk_probability"] is None
    assert "FILL_POLICY_DEPRECATED_INTERNAL_ONLY" in oneshot_fill["warnings"]


def test_api_returns_business_fields_without_internal_algorithm_metrics() -> None:
    from app.api.routes_user_top_entities import get_user_top_entity_service
    from app.services.user_top_entity_service import TopEntityService, UserManufacturerScopeService

    app.dependency_overrides[get_user_top_entity_service] = lambda: TopEntityService(
        _repository(),
        scope_service=UserManufacturerScopeService.from_rows(_scope_rows()),
    )
    try:
        response = TestClient(app).get(
            "/api/risk/my/top-entities",
            params={"top_n": 1},
            headers={"X-User-Id": "user_a"},
        )
    finally:
        app.dependency_overrides.pop(get_user_top_entity_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == "user_a"
    assert payload["top_n"] == 1
    assert payload["group_by"] == "user_scope"
    assert payload["ranking_strategy"] == "probability"
    assert payload["scope"]["manufacturer_codes"] == ["M1", "M2"]
    text = json.dumps(payload)
    for forbidden in ["AUC", "ECE", "PR-AUC", "XGBoost", "feature ablation", "leakage audit"]:
        assert forbidden not in text


def test_api_rejects_top_n_below_one_with_400() -> None:
    response = TestClient(app).get(
        "/api/risk/my/top-entities",
        params={"top_n": 0},
        headers={"X-User-Id": "user_a"},
    )

    assert response.status_code == 400
    assert "top_n must be >= 1" in response.json()["detail"]


def test_top_n_above_max_is_clamped_with_warning() -> None:
    from app.services.user_top_entity_service import TopEntityService, UserManufacturerScopeService

    payload = TopEntityService(
        _repository(),
        scope_service=UserManufacturerScopeService.from_rows(_scope_rows()),
    ).list_user_top_entities(
        user_id="user_a",
        top_n=5,
        max_n=1,
        ranking_strategy="probability",
    )

    assert payload["requested_top_n"] == 5
    assert payload["top_n"] == 1
    assert payload["groups"][0]["returned_count"] == 1
    assert "TOP_N_CLAMPED_TO_MAX_N" in payload["warnings"]


def test_default_policy_does_not_fill_or_apply_threshold_overflow() -> None:
    from app.services.user_top_entity_service import TopEntityService, UserManufacturerScopeService

    payload = TopEntityService(
        _repository(),
        scope_service=UserManufacturerScopeService.from_rows(_scope_rows()),
    ).list_user_top_entities(
        user_id="user_b",
        manufacturer_codes=["M4"],
        top_n=2,
        ranking_strategy="probability",
    )

    group = payload["groups"][0]
    assert payload["fill_policy"] == "none"
    assert payload["include_threshold_overflow"] is False
    assert group["returned_count"] == 1
    assert group["shortage_count"] == 1
    assert group["threshold_hit_count"] == 0
    assert group["overflow_count"] == 0
    assert [entity["candidate_type"] for entity in group["entities"]] == ["recurring"]


def test_frontend_risk_entities_api_reuses_top_entity_service() -> None:
    from app.api.routes_user_top_entities import get_user_top_entity_service
    from app.services.user_top_entity_service import TopEntityService, UserManufacturerScopeService

    app.dependency_overrides[get_user_top_entity_service] = lambda: TopEntityService(
        _repository(),
        scope_service=UserManufacturerScopeService.from_rows(_scope_rows()),
    )
    try:
        response = TestClient(app).get(
            "/api/v1/risk-entities",
            params={"top_n": 2},
            headers={"X-User-Id": "user_a"},
        )
    finally:
        app.dependency_overrides.pop(get_user_top_entity_service, None)

    assert response.status_code == 200
    entities = response.json()["entities"]
    assert [item["entity_id"] for item in entities] == ["m1_high", "m2_high"]
    assert len(entities) == 2


def test_user_top_entities_prefers_entity_display_lookup_names() -> None:
    from app.services.user_top_entity_service import TopEntityService, UserManufacturerScopeService

    payload = TopEntityService(
        _repository(),
        scope_service=UserManufacturerScopeService.from_rows(_scope_rows()),
    ).list_user_top_entities(
        user_id="user_a",
        top_n=1,
        ranking_strategy="probability",
    )

    entity = payload["groups"][0]["entities"][0]
    assert entity["risk_entity_id"] == "m1_high"
    assert entity["manufacturer_display_name"] == "Lookup Manufacturer M1"
    assert entity["hospital_display_name"] == "Lookup Hospital m1_high"
    assert entity["drug_display_name"] == "Lookup Drug m1_high"
    assert entity["region_display_name"] == "Lookup Region m1_high"
    assert "DISPLAY_LOOKUP_MISSING" not in payload["warnings"]


def test_formal_top_entity_path_does_not_import_algo_main_or_raw_source_db() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sources = [
        project_root / "app" / "api" / "routes_user_top_entities.py",
        project_root / "app" / "api" / "routes_frontend_pages.py",
        project_root / "app" / "services" / "user_top_entity_service.py",
        project_root / "app" / "services" / "frontend_top_entity_adapter.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in sources)

    for forbidden in [
        "algo_main",
        "DATABASE_URL",
        "sql_table_adapter",
        "backbone_service",
        "app.algorithms",
        "front_end",
    ]:
        assert forbidden not in text


def test_frontend_does_not_read_result_batch_directly() -> None:
    frontend_src = Path(__file__).resolve().parents[2] / "front_end" / "src"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in frontend_src.rglob("*") if path.is_file()
    )

    for forbidden in [
        "risk_result_batch",
        "RISK_RESULT_BATCH_DIR",
        "ParquetRiskResultRepository",
        "risk_model_core",
    ]:
        assert forbidden not in source


def _repository() -> InMemoryRiskResultRepository:
    return InMemoryRiskResultRepository(
        _manifest(),
        {
            "risk_entities": pd.DataFrame(
                [
                    _entity("m1_high", "M1", 0.95),
                    _entity("m1_second_threshold", "M1", 0.88),
                    _entity("m1_low", "M1", 0.20),
                    _entity("m2_high", "M2", 0.90),
                    _entity("m2_low", "M2", 0.30),
                    _entity("m3_forbidden", "M3", 0.99),
                    _entity("m4_recurring", "M4", 0.70),
                    _entity("m4_observation", "M4", None, is_observation=True),
                    _entity("m5_recurring", "M5", 0.60),
                    _entity("m5_oneshot", "M5", None, is_one_shot=True, risk_score_display=0.83),
                ]
            ),
            "entity_display_lookup": _entity_display_lookup(),
        },
    )


def _entity(
    entity_id: str,
    manufacturer_code: str,
    risk_probability: float | None,
    *,
    is_observation: bool = False,
    is_one_shot: bool = False,
    risk_score_display: float = 0.0,
) -> dict[str, object]:
    candidate_type = "recurring"
    if is_observation:
        candidate_type = "observation"
    if is_one_shot:
        candidate_type = "one_shot"
    return {
        "risk_entity_id": entity_id,
        "candidate_id": entity_id + "|H6",
        "tenant_id": "tenant",
        "enterprise_id": "enterprise",
        "manufacturer_code": manufacturer_code,
        "manufacturer_display_name": f"{manufacturer_code} display",
        "hospital_code": entity_id + "_hospital",
        "hospital_display_name": entity_id + " hospital",
        "drug_code": entity_id + "_drug",
        "drug_group": entity_id + "_drug",
        "drug_display_name": entity_id + " drug",
        "report_month": "2025-12",
        "primary_horizon": "H6",
        "risk_probability_value": risk_probability,
        "risk_probability_display": "hidden" if risk_probability is None else "risk band",
        "risk_score_display": risk_score_display,
        "risk_level": "orange" if risk_probability and risk_probability >= 0.8 else "yellow",
        "risk_color": "orange",
        "risk_type_label": candidate_type,
        "region_display_name": "江苏省",
        "review_status": candidate_type,
        "final_candidate_status": candidate_type,
        "review_priority": "P1",
        "risk_card_count": 1,
        "is_high_risk": bool(
            risk_probability and risk_probability >= 0.8 and not is_observation and not is_one_shot
        ),
        "is_observation": is_observation,
        "is_one_shot": is_one_shot,
        "is_probability_allowed": risk_probability is not None,
        "auto_dispatch_allowed": False,
        "main_reason_summary": "safe reason",
        "suggested_action_short": "review",
    }


def _scope_rows() -> list[dict[str, object]]:
    return [
        {
            "user_id": "user_a",
            "manufacturer_code": "M1",
            "manufacturer_display_name": "M1 display",
            "enabled": True,
        },
        {
            "user_id": "user_a",
            "manufacturer_code": "M2",
            "manufacturer_display_name": "M2 display",
            "enabled": True,
        },
        {
            "user_id": "user_b",
            "manufacturer_code": "M4",
            "manufacturer_display_name": "M4 display",
            "enabled": True,
        },
        {
            "user_id": "user_b",
            "manufacturer_code": "M5",
            "manufacturer_display_name": "M5 display",
            "enabled": True,
        },
    ]


def _entity_display_lookup() -> pd.DataFrame:
    rows = []
    for entity_id, manufacturer_code in [
        ("m1_high", "M1"),
        ("m2_high", "M2"),
        ("m4_recurring", "M4"),
        ("m5_recurring", "M5"),
    ]:
        drug_group = entity_id + "_drug"
        rows.append(
            {
                "tenant_id": "tenant",
                "report_month": "2025-12",
                "manufacturer_code": manufacturer_code,
                "manufacturer_display_name": f"Lookup Manufacturer {manufacturer_code}",
                "hospital_code": entity_id + "_hospital",
                "hospital_display_name": f"Lookup Hospital {entity_id}",
                "drug_code": drug_group,
                "drug_group": drug_group,
                "drug_display_name": f"Lookup Drug {entity_id}",
                "product_line_code": "",
                "product_line_name": "",
                "region_code": "lookup_region",
                "region_display_name": f"Lookup Region {entity_id}",
                "display_key": f"tenant|2025-12|{manufacturer_code}|{entity_id}_hospital|{drug_group}",
                "display_name_source": "master",
                "display_name_quality": "master",
                "source_raw_batch_id": "raw-test",
                "updated_at": "2026-07-08T00:00:00+00:00",
            }
        )
    return pd.DataFrame(rows)


def _manifest() -> RiskResultManifest:
    return RiskResultManifest(
        batch_id="batch",
        report_type="monthly",
        report_month="2025-12",
        report_date="2025-12-31",
        score_cutoff_month="2025-12",
        primary_horizon="H6",
        available_horizons=["H3", "H6", "H12"],
        schema_version="test",
        data_backend="memory",
        allowed_usage=["test"],
        forbidden_usage=[],
        customer_facing_probability_service_allowed=False,
        auto_dispatch_allowed=False,
        proof_case_report_allowed=False,
        caveats=["bounded monthly worklist"],
        raw={"batch_id": "batch"},
    )
