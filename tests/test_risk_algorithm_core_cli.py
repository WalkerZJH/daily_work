from __future__ import annotations

import subprocess
import sys

from tests.risk_algorithm_core_test_utils import REPO_ROOT, RUN_CONFIG


def test_cli_validate_raw_and_dry_run(tmp_path) -> None:
    validate = subprocess.run(
        [
            sys.executable,
            "-m",
            "risk_algorithm_core.cli",
            "validate-raw",
            "--raw-batch",
            "tests/fixtures/risk_raw_input_minimal",
            "--schema-mapping",
            "configs/risk_algorithm_core/schema_mapping.example.yaml",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "raw_input_validation: ok" in validate.stdout

    dry = subprocess.run(
        [
            sys.executable,
            "-m",
            "risk_algorithm_core.cli",
            "dry-run",
            "--config",
            str(RUN_CONFIG),
            "--use-rule-baseline",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "monthly_dry_run: ok" in dry.stdout
