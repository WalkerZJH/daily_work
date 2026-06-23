from __future__ import annotations

from typing import Any

from app.core.config import load_config
from app.schemas.api import ConfigDryRunRequest, ConfigDryRunResponse, DataSourceRequest
from app.schemas.config import AppConfig
from app.services.inspection_service import InspectionService


class ConfigService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def current_config(self) -> dict[str, Any]:
        return self.config.model_dump(mode="json")

    def dry_run_patch(self, request: ConfigDryRunRequest) -> ConfigDryRunResponse:
        source = DataSourceRequest(dataset_name=request.dataset_name, csv_path=request.csv_path)
        default_result = InspectionService(self.config).dry_run(source, request.as_of_date)
        patched_config = load_config(patch=request.config_patch)
        patched_result = InspectionService(patched_config).dry_run(source, request.as_of_date)
        return ConfigDryRunResponse(
            default_result=default_result,
            patched_result=patched_result,
            delta={
                "clue_count": patched_result.clue_count - default_result.clue_count,
                "risk_level_distribution": _dict_delta(
                    default_result.risk_level_distribution,
                    patched_result.risk_level_distribution,
                ),
                "detector_hit_distribution": _dict_delta(
                    default_result.detector_hit_distribution,
                    patched_result.detector_hit_distribution,
                ),
            },
        )


def _dict_delta(base: dict[str, int], patched: dict[str, int]) -> dict[str, int]:
    keys = set(base) | set(patched)
    return {key: patched.get(key, 0) - base.get(key, 0) for key in sorted(keys)}
