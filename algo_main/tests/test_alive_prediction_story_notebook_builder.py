from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def test_alive_prediction_model_selection_notebook_builder_runs():
    root = Path(__file__).resolve().parents[1]
    notebook = root / "notebooks/02_alive_prediction_model_selection_story.ipynb"
    result = subprocess.run(
        [sys.executable, "scripts/rebuild_alive_prediction_model_selection_notebook.py"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert str(notebook) in result.stdout
    assert notebook.is_file()
    data = json.loads(notebook.read_text(encoding="utf-8"))
    source = "\n".join("".join(cell.get("source", [])) for cell in data["cells"])
    for expected in [
        "Alive Prediction 模型选型与决策链路复核",
        "时间漂移分析",
        "Feature stability v1 与 calibration v2",
        "Demand-shape routing 与标签口径审查",
        "probability_candidate_v1 = logistic_regression + frequency_decay_v1 + raw",
    ]:
        assert expected in source

