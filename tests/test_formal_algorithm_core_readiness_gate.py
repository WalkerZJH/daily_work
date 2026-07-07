from __future__ import annotations

from tests.formal_raw_to_batch_test_utils import REPORT_DIR


def test_formal_readiness_gate_is_explicit_about_conditional_status() -> None:
    gate = REPORT_DIR / "formal_algorithm_core_readiness_gate.md"
    if not gate.exists():
        raise AssertionError("formal readiness gate report is missing")
    text = gate.read_text(encoding="utf-8")
    assert "raw_input_contract_ready" in text
    assert "artifact_score_parity_passed" in text
    assert "monthly_runner_formal_mode_ready" in text
    assert "result_batch_model_core_readable" in text
    assert "formal_second_layer_conditional" in text
