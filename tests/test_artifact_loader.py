from __future__ import annotations

import pytest

from risk_algorithm_core.artifact_loader import load_current_model_artifact
from tests.risk_algorithm_core_test_utils import MODEL_FIXTURE


def test_artifact_loader_reads_fixture_artifact() -> None:
    artifact = load_current_model_artifact(MODEL_FIXTURE, require_artifact=True)
    assert artifact.manifest.artifact_id == "fixture_linear_stub_v1"
    assert artifact.model["type"] == "linear_stub"


def test_formal_run_missing_artifact_fails(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_current_model_artifact(tmp_path / "missing", require_artifact=True)
