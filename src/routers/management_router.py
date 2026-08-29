import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.database import User
from src.models.schemas import (
    TrainingTaskResponse, KnowledgeBaseCreate, KnowledgeBaseResponse,
    RestrictionProfileCreate, RestrictionProfileResponse, RestrictionProfileUpdate,
    WebCrawlRequest, ResourceStats, ResourceAllocationUpdate, SuccessResponse
)
from src.middleware.auth_middleware import get_current_user
from src.services.management_service import management_service

router = APIRouter(prefix="/management", tags=["Management"])

UPLOAD_DIR = "/www/AI_server/data/uploads"


@router.get("/models")
async def list_models_with_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    from src.services.user_settings_service import user_settings_service
    settings = user_settings_service.get_or_create_settings(db, current_user.id)
    models = management_service.get_model_recommendations(settings.default_model)
    return {"models": models, "current_model": settings.default_model}


@router.get("/models/{model_id}/info")
async def get_model_info(
    model_id: str,
    current_user: User = Depends(get_current_user)
):
    from src.inference.ollama_client import ollama_client
    try:
        info = await ollama_client.get_model_info(model_id)
        if not info:
            raise HTTPException(status_code=404, detail="Model not found")

        from src.services.management_service import MODEL_CAPABILITIES, MODEL_RECOMMENDATIONS
        return {
            "id": model_id,
            "details": info,
            "capabilities": MODEL_CAPABILITIES.get(model_id, ["general"]),
            "recommendation": MODEL_RECOMMENDATIONS.get(model_id, "balanced"),
            "lighter_models": management_service.get_lighter_models(model_id)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train/pdf")
async def upload_pdf_for_training(
    file: UploadFile = File(...),
    kb_name: str = Form(...),
    model_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, f"{current_user.id}_{uuid.uuid4().hex}.pdf")

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    task = management_service.create_training_task(
        db, current_user.id,
        type("obj", (object,), {"task_type": "pdf", "model_id": model_id, "source_info": {"file_path": file_path, "filename": file.filename}})()
    )

    management_service.start_pdf_task(db, task.id, file_path, kb_name, model_id)

    return {
        "task_id": task.id,
        "status": "pending",
        "message": "PDF processing started in background"
    }


@router.post("/train/web")
async def start_web_crawl(
    request: WebCrawlRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    task = management_service.create_training_task(
        db, current_user.id,
        type("obj", (object,), {
            "task_type": "web_crawl",
            "model_id": request.model_id,
            "source_info": {"url": request.url, "max_pages": request.max_pages}
        })()
    )

    kb_name = f"Web: {request.url[:50]}"
    management_service.start_web_crawl_task(
        db, task.id, request.url, request.max_pages, kb_name, request.model_id
    )

    return {
        "task_id": task.id,
        "status": "pending",
        "message": "Web crawl started in background"
    }


@router.get("/tasks")
async def list_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    tasks = management_service.get_training_tasks(db, current_user.id)
    return [TrainingTaskResponse.model_validate(t) for t in tasks]


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    task = management_service.get_training_task(db, task_id, current_user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TrainingTaskResponse.model_validate(task)


@router.delete("/tasks/{task_id}")
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = management_service.cancel_task(db, task_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or cannot be cancelled")
    return SuccessResponse(message="Task cancelled")


@router.get("/knowledge-bases")
async def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    kbs = management_service.get_knowledge_bases(db, current_user.id)
    return [KnowledgeBaseResponse.model_validate(kb) for kb in kbs]


@router.post("/knowledge-bases")
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    kb = management_service.create_knowledge_base(db, current_user.id, data)
    return KnowledgeBaseResponse.model_validate(kb)


@router.delete("/knowledge-bases/{kb_id}")
async def delete_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = management_service.delete_knowledge_base(db, kb_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return SuccessResponse(message="Knowledge base deleted")


@router.post("/knowledge-bases/{kb_id}/toggle")
async def toggle_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    kb = management_service.toggle_knowledge_base(db, kb_id, current_user.id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return KnowledgeBaseResponse.model_validate(kb)


@router.post("/restrictions")
async def create_restriction(
    data: RestrictionProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    profile = management_service.create_restriction_profile(db, current_user.id, data)
    return RestrictionProfileResponse.model_validate(profile)


@router.get("/restrictions")
async def list_restrictions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    profiles = management_service.get_restriction_profiles(db, current_user.id)
    return [RestrictionProfileResponse.model_validate(p) for p in profiles]


@router.put("/restrictions/{profile_id}")
async def update_restriction(
    profile_id: str,
    data: RestrictionProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    profile = management_service.update_restriction_profile(db, profile_id, current_user.id, data)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return RestrictionProfileResponse.model_validate(profile)


@router.delete("/restrictions/{profile_id}")
async def delete_restriction(
    profile_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = management_service.delete_restriction_profile(db, profile_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Profile not found")
    return SuccessResponse(message="Profile deleted")


@router.post("/restrictions/{profile_id}/activate")
async def activate_restriction(
    profile_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = management_service.activate_restriction_profile(db, profile_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Profile not found")
    return SuccessResponse(message="Profile activated")


@router.post("/restrictions/deactivate")
async def deactivate_restrictions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    management_service.deactivate_all_restrictions(db, current_user.id)
    return SuccessResponse(message="All restrictions deactivated")


@router.get("/resources")
async def get_resources(
    current_user: User = Depends(get_current_user)
):
    resources = management_service.get_system_resources()
    return resources


@router.put("/resources/allocation")
async def update_resource_allocation(
    data: ResourceAllocationUpdate,
    current_user: User = Depends(get_current_user)
):
    return SuccessResponse(
        message="Resource allocation updated",
        data={"max_concurrent_tasks": data.max_concurrent_tasks, "max_memory_percent": data.max_memory_percent}
    )
