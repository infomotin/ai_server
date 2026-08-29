from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.schemas import ModelInfo, ModelListResponse
from src.services.model_service import model_service
from src.middleware.auth_middleware import get_api_key
from src.models.database import APIKey
from src.inference.ollama_client import ollama_client

router = APIRouter(prefix="/v1/models", tags=["Models"])


@router.get("", response_model=ModelListResponse)
async def list_models(
    api_key: APIKey = Depends(get_api_key),
    db: Session = Depends(get_db_session)
):
    await model_service.sync_with_ollama(db)

    models = model_service.get_all_models(db)

    model_list = []
    for model in models:
        model_list.append(ModelInfo(
            id=model.id,
            name=model.name,
            provider=model.provider,
            size_bytes=model.size_bytes,
            parameter_count=model.parameter_count,
            quantization=model.quantization,
            is_downloaded=model.is_downloaded
        ))

    return ModelListResponse(data=model_list)


@router.get("/{model_id}", response_model=ModelInfo)
async def get_model(
    model_id: str,
    api_key: APIKey = Depends(get_api_key),
    db: Session = Depends(get_db_session)
):
    model = model_service.get_model(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    return ModelInfo(
        id=model.id,
        name=model.name,
        provider=model.provider,
        size_bytes=model.size_bytes,
        parameter_count=model.parameter_count,
        quantization=model.quantization,
        is_downloaded=model.is_downloaded
    )


@router.post("/{model_id}/download")
async def download_model(
    model_id: str,
    api_key: APIKey = Depends(get_api_key),
    db: Session = Depends(get_db_session)
):
    model = model_service.get_model(db, model_id)
    if model and model.is_downloaded:
        return {"status": "already_downloaded", "model": model_id}

    result = await model_service.download_model(db, model_id)
    return result
