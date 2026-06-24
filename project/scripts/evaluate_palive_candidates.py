from __future__ import annotations

import argparse

from app.core.config import load_config
from app.schemas.api import PAliveExperimentRequest
from app.services.palive_experiment_service import PAliveExperimentService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-name", default="sample")
    parser.add_argument("--as-of-date", required=True)
    args = parser.parse_args()
    request = PAliveExperimentRequest(dataset_name=args.dataset_name, as_of_date=args.as_of_date)
    response = PAliveExperimentService(load_config()).run_experiment(
        request,
        request.as_of_date,
        request.enabled_models,
    )
    print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
