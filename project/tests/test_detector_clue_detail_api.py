from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
import numpy as np
import pandas as pd

from app.main import app
from app.services.detector_result_service import _safe_evidence_payload
from project.tests.detector_result_test_utils import make_detector_repository, override_detector_service


def test_rule_only_clue_detail_returns_rule_facts_without_candidate_fields() -> None:
    with override_detector_service():
        response = TestClient(app).get("/api/v1/detectors/clues/clue_non_high")

    assert response.status_code == 200
    payload = response.json()
    item = payload["item"]
    assert item["detector_clue_id"] == "clue_non_high"
    assert item["risk_entity_id"] == ""
    assert item["monthly_risk_probability"] is None
    assert item["evidence_text"]
    assert item["evidence_payload"] == {}
    assert item["evaluation"]["current_value"] == 1.0
    assert item["evaluation"]["baseline_value"] == 4.0
    assert item["evaluation"]["threshold_value"] == 0.6
    assert item["evaluation"]["config_id"] == "cfg-2"
    assert "detector_score is rule inspection score, not probability" in payload["semantic_caveats"]
    assert "daily detector clues do not create risk_entities" in payload["semantic_caveats"]


def test_detector_clue_detail_returns_404_for_unknown_or_context_mismatch() -> None:
    with override_detector_service():
        missing = TestClient(app).get("/api/v1/detectors/clues/not-a-clue")
        mismatch = TestClient(app).get(
            "/api/v1/detectors/clues/clue_non_high",
            params={"manufacturer_code": "another-manufacturer"},
        )

    assert missing.status_code == 404
    assert mismatch.status_code == 404


def test_detector_clue_detail_rejects_duplicate_identifier_without_leaking_storage_details() -> None:
    repository = make_detector_repository()
    repository.tables["daily_detector_clues"] = pd.concat(
        [repository.tables["daily_detector_clues"], repository.tables["daily_detector_clues"].iloc[[1]]],
        ignore_index=True,
    )
    with override_detector_service(repository):
        response = TestClient(app).get("/api/v1/detectors/clues/clue_non_high")

    assert response.status_code == 500
    assert response.json()["detail"] == "Detector clue detail is unavailable"


def test_evidence_payload_serialization_handles_missing_numpy_dates_and_nested_values() -> None:
    payload = _safe_evidence_payload(
        {
            "missing": np.nan,
            "score": np.float64(0.76),
            "observed_at": date(2025, 12, 31),
            "nested": {"empty": pd.NA, "items": [np.int64(2), None]},
        }
    )

    assert payload == {
        "missing": None,
        "score": 0.76,
        "observed_at": "2025-12-31",
        "nested": {"empty": None, "items": [2, None]},
    }
