from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from app.core.config import PROJECT_ROOT, load_config
from app.schemas.training import TrainingDatasetBuildRequest
from app.services.training_dataset_service import TrainingDatasetService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/palive_training.yaml")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    with config_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}
    source = raw.get("source") or {}
    request = TrainingDatasetBuildRequest(
        source_type=source.get("source_type", "csv"),
        dataset_name=source.get("dataset_name", "sample"),
        csv_path=source.get("csv_path"),
        enterprise_code=source.get("enterprise_code"),
        province=source.get("province"),
        province_code=source.get("province_code"),
        row_limit=source.get("row_limit"),
        train_start=raw["train_start"],
        train_end=raw["train_end"],
        horizon_days=raw.get("horizon_days", 90),
        freq=raw.get("origin_freq", "M"),
        output_path=args.output or raw.get("output_path"),
    )
    response = TrainingDatasetService(load_config()).build_dataset(request)
    print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
