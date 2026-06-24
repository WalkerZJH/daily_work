from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_app_config
from app.schemas.config import AppConfig
from app.schemas.training import TrainingDatasetBuildRequest, TrainingDatasetBuildResponse
from app.services.training_dataset_service import TrainingDatasetService

router = APIRouter(prefix="/api/v0/training", tags=["training"])


@router.post("/build-dataset", response_model=TrainingDatasetBuildResponse)
def build_training_dataset(
    request: TrainingDatasetBuildRequest,
    config: AppConfig = Depends(get_app_config),
) -> TrainingDatasetBuildResponse:
    return TrainingDatasetService(config).build_dataset(request)
