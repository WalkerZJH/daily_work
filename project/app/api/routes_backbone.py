from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends

from app.api.deps import get_app_config
from app.schemas.api import (
    PAliveExperimentConfig,
    PAliveExperimentRequest,
    PAliveExperimentResponse,
)
from app.schemas.backbone import BackbonePredictRequest, BackbonePredictResponse
from app.schemas.config import AppConfig
from app.services.backbone_service import BackboneService
from app.services.palive_experiment_service import PAliveExperimentService

router = APIRouter(prefix="/api/v0/backbone", tags=["backbone"])


@router.get("/palive/config", response_model=PAliveExperimentConfig)
def get_palive_config(config: AppConfig = Depends(get_app_config)) -> PAliveExperimentConfig:
    return PAliveExperimentService(config).get_config()


@router.patch("/palive/config", response_model=PAliveExperimentConfig)
def patch_palive_config(
    patch: dict[str, Any] = Body(default_factory=dict),
    config: AppConfig = Depends(get_app_config),
) -> PAliveExperimentConfig:
    return PAliveExperimentService(config).patch_config(patch)


@router.post("/palive/experiment", response_model=PAliveExperimentResponse)
def run_palive_experiment(
    request: PAliveExperimentRequest,
    config: AppConfig = Depends(get_app_config),
) -> PAliveExperimentResponse:
    return PAliveExperimentService(config).run_experiment(
        request,
        request.as_of_date,
        request.enabled_models,
    )


@router.post("/predict", response_model=BackbonePredictResponse)
def predict_backbone(
    request: BackbonePredictRequest,
    config: AppConfig = Depends(get_app_config),
) -> BackbonePredictResponse:
    return BackboneService(config).predict_with_summary(request)
