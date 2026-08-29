import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.database import User
from src.models.schemas import (
    CustomModelCreate, CustomModelUpdate, CustomModelResponse,
    ModelTrainFromPDF, ModelTrainFromText, ModelTrainFromWeb, SuccessResponse
)
from src.middleware.auth_middleware import get_current_user
from src.services.model_builder_service import model_builder_service

router = APIRouter(prefix="/model-builder", tags=["Model Builder"])

UPLOAD_DIR = "/www/AI_server/data/uploads"


class LightweightModelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    task_type: str = Field(..., pattern="^(simple_math|greeting_bot|color_sayer|yes_no_bot|word_counter|date_helper|garment_specialist|account_bot)$")
    base_model: str = Field(default="qwen2.5:0.5b")
    custom_knowledge: Optional[str] = None
    custom_prompt: Optional[str] = None


@router.get("/templates")
async def get_domain_templates(
    current_user: User = Depends(get_current_user)
):
    templates = model_builder_service.get_domain_templates()
    return {"templates": templates}


@router.get("/templates/{domain}")
async def get_domain_template(
    domain: str,
    current_user: User = Depends(get_current_user)
):
    template = model_builder_service.get_domain_template(domain)
    if not template:
        raise HTTPException(status_code=404, detail="Domain template not found")
    return {
        "domain": template.domain,
        "name": template.name,
        "description": template.description,
        "icon": template.icon,
        "color": template.color,
        "default_prompt": template.default_prompt,
        "default_topics": template.default_topics,
        "suggested_base_model": template.suggested_base_model
    }


@router.post("/models")
async def create_custom_model(
    data: CustomModelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    model = model_builder_service.create_custom_model(db, current_user.id, data)
    return CustomModelResponse.model_validate(model)


@router.get("/models")
async def list_custom_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    models = model_builder_service.get_custom_models(db, current_user.id)
    return [CustomModelResponse.model_validate(m) for m in models]


@router.get("/models/{model_id}")
async def get_custom_model(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    model = model_builder_service.get_custom_model(db, model_id, current_user.id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return CustomModelResponse.model_validate(model)


@router.put("/models/{model_id}")
async def update_custom_model(
    model_id: str,
    data: CustomModelUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    model = model_builder_service.update_custom_model(db, model_id, current_user.id, data)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return CustomModelResponse.model_validate(model)


@router.delete("/models/{model_id}")
async def delete_custom_model(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = model_builder_service.delete_custom_model(db, model_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    return SuccessResponse(message="Custom model deleted")


@router.post("/models/{model_id}/train/pdf")
async def train_model_pdf(
    model_id: str,
    file: UploadFile = File(...),
    chunk_size: int = Form(1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, f"model_{model_id}_{uuid.uuid4().hex}.pdf")

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    success = model_builder_service.train_model_from_pdf(db, model_id, current_user.id, file_path, chunk_size)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")

    return SuccessResponse(
        message="PDF training started in background",
        data={"model_id": model_id, "file": file.filename}
    )


@router.post("/models/{model_id}/train/text")
async def train_model_text(
    model_id: str,
    data: ModelTrainFromText,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = model_builder_service.train_model_from_text(
        db, model_id, current_user.id, data.text, data.chunk_size
    )
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")

    return SuccessResponse(
        message="Text training started in background",
        data={"model_id": model_id, "text_length": len(data.text)}
    )


@router.post("/models/{model_id}/train/web")
async def train_model_web(
    model_id: str,
    data: ModelTrainFromWeb,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = model_builder_service.train_model_from_web(
        db, model_id, current_user.id, data.url, data.max_pages
    )
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")

    return SuccessResponse(
        message="Web training started in background",
        data={"model_id": model_id, "url": data.url}
    )


@router.get("/models/{model_id}/prompt")
async def get_model_prompt(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    model = model_builder_service.get_custom_model(db, model_id, current_user.id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    full_prompt = model_builder_service.build_system_prompt_for_model(model)
    return {
        "model_id": model.id,
        "model_name": model.name,
        "system_prompt": model.system_prompt,
        "full_prompt": full_prompt,
        "knowledge_chars": model.total_chars,
        "chunk_count": model.chunk_count
    }


@router.get("/stats")
async def get_usage_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    stats = model_builder_service.get_model_usage_stats(db, current_user.id)
    return stats


@router.get("/lightweight/tasks")
async def get_lightweight_task_types(
    current_user: User = Depends(get_current_user)
):
    tasks = model_builder_service.get_lightweight_task_types()
    return {"tasks": tasks}


@router.post("/lightweight/create")
async def create_lightweight_model(
    data: LightweightModelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    model = model_builder_service.create_lightweight_model(
        db=db,
        user_id=current_user.id,
        name=data.name,
        task_type=data.task_type,
        base_model=data.base_model,
        custom_knowledge=data.custom_knowledge,
        custom_prompt=data.custom_prompt
    )
    return CustomModelResponse.model_validate(model)
