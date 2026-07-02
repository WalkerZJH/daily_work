from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def test_candidate_refinement_story_notebook_builder_runs():
    root = Path(__file__).resolve().parents[1]
    notebook = root / "notebooks/03_alive_prediction_candidate_refinement_story.ipynb"
    result = subprocess.run(
        [sys.executable, "scripts/rebuild_alive_prediction_candidate_refinement_notebook.py"],
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
        "Alive Prediction M1-M7 主干算法链路展示",
        "本阶段已经完成从概率 scorer 到结构化线索材料与静态样式原型的闭环",
        "## 3. M1 业务候选池",
        "## 5. M2 one-shot repeat propensity",
        "## 6. M3 survival-lite",
        "## 7. M4 detector evidence",
        "## 8. M5 candidate status decision",
        "## 9. M7 structured evidence bundle",
        "## 11. 静态线索卡样式原型",
        "M6 cache 未实现",
        "auto_dispatch_allowed",
    ]:
        assert expected in source


def test_candidate_refinement_notebook_has_no_training_or_llm_calls():
    root = Path(__file__).resolve().parents[1]
    notebook = root / "notebooks/03_alive_prediction_candidate_refinement_story.ipynb"
    if not notebook.exists():
        subprocess.run(
            [sys.executable, "scripts/rebuild_alive_prediction_candidate_refinement_notebook.py"],
            cwd=root,
            check=True,
        )
    source = notebook.read_text(encoding="utf-8")
    forbidden = [
        "read_parquet",
        ".fit(",
        "fit(",
        "OpenAI",
        "chat.completions",
        "responses.create",
        "run_alive_prediction_candidate_pool_v1",
        "run_alive_prediction_survival_lite_v1",
        "run_alive_prediction_detectors_v1",
        "run_alive_prediction_status_decision_v1",
    ]
    for item in forbidden:
        assert item not in source
