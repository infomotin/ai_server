from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.database import User
from src.middleware.auth_middleware import get_current_user
from src.services.ai_assistant_service import ai_assistant_service

router = APIRouter(prefix="/assistants", tags=["AI Assistants"])


class AssistantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    template: str = Field(default="custom")
    model_id: str = Field(default="llama3.2:1b")
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    personality: str = Field(default="professional")


class AssistantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model_id: Optional[str] = None
    system_prompt: Optional[str] = None
    personality: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    is_active: Optional[bool] = None
    auto_reply: Optional[bool] = None


class IntegrationUpdate(BaseModel):
    config: Optional[Dict[str, Any]] = None
    credentials: Optional[str] = None
    is_active: Optional[bool] = None


class TaskCreate(BaseModel):
    task_type: str
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    schedule: Optional[str] = None


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    schedule: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/templates")
async def get_templates(current_user: User = Depends(get_current_user)):
    return ai_assistant_service.get_templates()


@router.get("/integration-types")
async def get_integration_types(current_user: User = Depends(get_current_user)):
    return ai_assistant_service.get_integration_types()


@router.get("/task-types")
async def get_task_types(current_user: User = Depends(get_current_user)):
    return ai_assistant_service.get_task_types()


@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    return ai_assistant_service.get_stats(db, current_user.id)


@router.get("")
async def list_assistants(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    assistants = ai_assistant_service.get_assistants(db, current_user.id)
    return [{
        "id": a.id, "name": a.name, "description": a.description,
        "avatar": a.avatar, "model_id": a.model_id, "personality": a.personality,
        "is_active": a.is_active, "auto_reply": a.auto_reply,
        "created_at": str(a.created_at)
    } for a in assistants]


@router.post("")
async def create_assistant(
    data: AssistantCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    assistant = ai_assistant_service.create_assistant(
        db=db, user_id=current_user.id, name=data.name,
        template=data.template, model_id=data.model_id,
        description=data.description, system_prompt=data.system_prompt,
        personality=data.personality
    )
    return {"id": assistant.id, "name": assistant.name}


@router.get("/{assistant_id}")
async def get_assistant(
    assistant_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    data = ai_assistant_service.get_assistant_with_details(db, assistant_id, current_user.id)
    if not data:
        raise HTTPException(status_code=404, detail="Assistant not found")

    assistant = data["assistant"]
    integrations = data["integrations"]
    tasks = data["tasks"]
    logs = data["recent_logs"]

    return {
        "assistant": {
            "id": assistant.id, "name": assistant.name, "description": assistant.description,
            "avatar": assistant.avatar, "model_id": assistant.model_id,
            "system_prompt": assistant.system_prompt, "personality": assistant.personality,
            "temperature": assistant.temperature, "max_tokens": assistant.max_tokens,
            "is_active": assistant.is_active, "auto_reply": assistant.auto_reply,
            "created_at": str(assistant.created_at)
        },
        "integrations": [{
            "id": i.id, "integration_type": i.integration_type, "name": i.name,
            "config": i.config, "is_active": i.is_active, "status": i.status,
            "last_sync": str(i.last_sync) if i.last_sync else None
        } for i in integrations],
        "tasks": [{
            "id": t.id, "task_type": t.task_type, "name": t.name,
            "description": t.description, "config": t.config, "schedule": t.schedule,
            "is_active": t.is_active, "last_run": str(t.last_run) if t.last_run else None,
            "run_count": t.run_count
        } for t in tasks],
        "recent_logs": [{
            "id": l.id, "action": l.action, "input_text": l.input_text[:200] if l.input_text else None,
            "output_text": l.output_text[:200] if l.output_text else None,
            "status": l.status, "tokens_used": l.tokens_used,
            "created_at": str(l.created_at)
        } for l in logs]
    }


@router.put("/{assistant_id}")
async def update_assistant(
    assistant_id: str,
    data: AssistantUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    assistant = ai_assistant_service.update_assistant(db, assistant_id, current_user.id, **update_data)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return {"id": assistant.id, "name": assistant.name}


@router.delete("/{assistant_id}")
async def delete_assistant(
    assistant_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = ai_assistant_service.delete_assistant(db, assistant_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return {"message": "Assistant deleted"}


@router.put("/integrations/{integration_id}")
async def update_integration(
    integration_id: str,
    data: IntegrationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    integration = ai_assistant_service.update_integration(db, integration_id, **update_data)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return {"id": integration.id, "status": integration.status}


@router.post("/{assistant_id}/tasks")
async def create_task(
    assistant_id: str,
    data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    task = ai_assistant_service.create_task(
        db=db, assistant_id=assistant_id, task_type=data.task_type,
        name=data.name, description=data.description,
        config=data.config, schedule=data.schedule
    )
    if not task:
        raise HTTPException(status_code=400, detail="Failed to create task")
    return {"id": task.id, "name": task.name}


@router.put("/tasks/{task_id}")
async def update_task(
    task_id: str,
    data: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    task = ai_assistant_service.update_task(db, task_id, **update_data)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"id": task.id, "name": task.name}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = ai_assistant_service.delete_task(db, task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted"}


@router.get("/{assistant_id}/logs")
async def get_logs(
    assistant_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    logs = ai_assistant_service.get_logs(db, assistant_id, limit)
    return [{
        "id": l.id, "action": l.action, "input_text": l.input_text[:200] if l.input_text else None,
        "output_text": l.output_text[:200] if l.output_text else None,
        "status": l.status, "tokens_used": l.tokens_used,
        "duration_ms": l.duration_ms, "created_at": str(l.created_at)
    } for l in logs]
