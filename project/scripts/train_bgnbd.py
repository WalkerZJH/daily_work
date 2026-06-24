from __future__ import annotations

import argparse
import json
from datetime import datetime

from app.core.config import PROJECT_ROOT


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/palive_training.yaml")
    args = parser.parse_args()
    output_dir = PROJECT_ROOT / "artifacts" / "models" / "palive_bgnbd" / datetime.now().strftime("%Y%m%d%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "model_card.json").open("w", encoding="utf-8") as file:
        json.dump(
            {
                "model_type": "bgnbd_candidate",
                "status": "placeholder",
                "config": args.config,
                "limitations": [
                    "候选接口占位",
                    "尚未完成真实拟合、回测和校准",
                    "不得解释为正式概率",
                ],
            },
            file,
            ensure_ascii=False,
            indent=2,
        )
    print(str(output_dir))


if __name__ == "__main__":
    main()
