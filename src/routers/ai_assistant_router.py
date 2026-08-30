from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
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
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    tags: Optional[List[str]] = None


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
    color: Optional[str] = None
    icon: Optional[str] = None
    tags: Optional[List[str]] = None


class IntegrationCreate(BaseModel):
    integration_type: str
    config: Optional[Dict[str, Any]] = None


class IntegrationUpdate(BaseModel):
    config: Optional[Dict[str, Any]] = None
    credentials: Optional[str] = None
    is_active: Optional[bool] = None
    name: Optional[str] = None
    status: Optional[str] = None


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


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    integration_type: Optional[str] = None
    conversation_id: Optional[str] = None


class RenameConversation(BaseModel):
    title: str


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
        "temperature": a.temperature, "max_tokens": a.max_tokens,
        "is_active": a.is_active, "auto_reply": a.auto_reply,
        "color": a.color, "tags": a.tags,
        "share_token": a.share_token,
        "created_at": str(a.created_at),
        "updated_at": str(a.updated_at) if a.updated_at else None
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
        personality=data.personality,
        temperature=data.temperature, max_tokens=data.max_tokens,
        color=data.color, icon=data.icon, tags=data.tags
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
    conversations = data["conversations"]

    return {
        "assistant": {
            "id": assistant.id, "name": assistant.name, "description": assistant.description,
            "avatar": assistant.avatar, "model_id": assistant.model_id,
            "system_prompt": assistant.system_prompt, "personality": assistant.personality,
            "temperature": assistant.temperature, "max_tokens": assistant.max_tokens,
            "is_active": assistant.is_active, "auto_reply": assistant.auto_reply,
            "color": assistant.color, "tags": assistant.tags,
            "share_token": assistant.share_token,
            "created_at": str(assistant.created_at),
            "updated_at": str(assistant.updated_at) if assistant.updated_at else None
        },
        "integrations": [{
            "id": i.id, "integration_type": i.integration_type, "name": i.name,
            "config": ai_assistant_service._normalize_config(i.config),
            "is_active": i.is_active, "status": i.status,
            "last_sync": str(i.last_sync) if i.last_sync else None,
            "created_at": str(i.created_at)
        } for i in integrations],
        "tasks": [{
            "id": t.id, "task_type": t.task_type, "name": t.name,
            "description": t.description, "config": ai_assistant_service._normalize_config(t.config),
            "schedule": t.schedule,
            "is_active": t.is_active, "last_run": str(t.last_run) if t.last_run else None,
            "next_run": str(t.next_run) if t.next_run else None,
            "run_count": t.run_count,
            "created_at": str(t.created_at)
        } for t in tasks],
        "conversations": [c if isinstance(c, dict) else {
            "id": c.id, "title": c.title,
            "created_at": str(c.created_at),
            "updated_at": str(c.updated_at) if c.updated_at else None,
            "message_count": getattr(c, 'message_count', 0)
        } for c in conversations],
        "recent_logs": [{
            "id": l.id, "action": l.action, "input_text": l.input_text[:200] if l.input_text else None,
            "output_text": l.output_text[:200] if l.output_text else None,
            "status": l.status, "tokens_used": l.tokens_used,
            "duration_ms": l.duration_ms, "created_at": str(l.created_at)
        } for l in logs]
    }


@router.post("/{assistant_id}/chat")
async def chat_with_assistant(
    assistant_id: str,
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    result = await ai_assistant_service.process_chat(
        db=db,
        assistant_id=assistant_id,
        user_id=current_user.id,
        message=data.message,
        conversation_id=data.conversation_id,
        integration_type=data.integration_type
    )
    return result


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


@router.post("/{assistant_id}/duplicate")
async def duplicate_assistant(
    assistant_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    clone = ai_assistant_service.duplicate_assistant(db, assistant_id, current_user.id)
    if not clone:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return {"id": clone.id, "name": clone.name}


@router.post("/{assistant_id}/toggle")
async def toggle_assistant(
    assistant_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    assistant = ai_assistant_service.get_assistant(db, assistant_id, current_user.id)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    assistant.is_active = not assistant.is_active
    db.commit()
    return {"id": assistant.id, "is_active": assistant.is_active}


@router.post("/{assistant_id}/share")
async def create_share_token(
    assistant_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    import secrets
    assistant = ai_assistant_service.get_assistant(db, assistant_id, current_user.id)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    if not assistant.share_token:
        assistant.share_token = secrets.token_urlsafe(24)
        db.commit()
    return {"share_token": assistant.share_token}


@router.delete("/{assistant_id}/share")
async def remove_share_token(
    assistant_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    assistant = ai_assistant_service.get_assistant(db, assistant_id, current_user.id)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    assistant.share_token = None
    db.commit()
    return {"share_token": None}


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


# ---------- Integrations ----------

@router.post("/{assistant_id}/integrations")
async def add_integration(
    assistant_id: str,
    data: IntegrationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    assistant = ai_assistant_service.get_assistant(db, assistant_id, current_user.id)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    integration = ai_assistant_service.add_integration(
        db, assistant_id, data.integration_type, data.config
    )
    return {"id": integration.id, "name": integration.name}


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


@router.delete("/integrations/{integration_id}")
async def delete_integration(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = ai_assistant_service.delete_integration(db, integration_id)
    if not success:
        raise HTTPException(status_code=404, detail="Integration not found")
    return {"message": "Integration deleted"}


@router.post("/integrations/{integration_id}/test")
async def test_integration(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    from src.services.integrations_service import integrations_service
    result = integrations_service.test_integration(db, integration_id, current_user.id)
    return result


# ---------- Tasks ----------

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


@router.post("/tasks/{task_id}/run")
async def run_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    result = ai_assistant_service.run_task(db, task_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Failed"))
    return result


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


# ---------- Conversations ----------

@router.get("/{assistant_id}/conversations")
async def list_conversations(
    assistant_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    assistant = ai_assistant_service.get_assistant(db, assistant_id, current_user.id)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    convs = ai_assistant_service.get_conversations(db, assistant_id)
    return [{
        "id": c.id, "title": c.title,
        "created_at": str(c.created_at),
        "updated_at": str(c.updated_at) if c.updated_at else None
    } for c in convs]


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    limit: int = Query(100, ge=1, le=500)
):
    from src.models.database import AssistantConversation
    conv = db.query(AssistantConversation).filter(
        AssistantConversation.id == conversation_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    assistant = ai_assistant_service.get_assistant(db, conv.assistant_id, current_user.id)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    messages = ai_assistant_service.get_messages(db, conversation_id, limit)
    return [{
        "id": m.id, "role": m.role, "content": m.content,
        "tokens_used": m.tokens_used, "duration_ms": m.duration_ms,
        "model": m.model, "error": m.error,
        "created_at": str(m.created_at)
    } for m in messages]


@router.put("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    data: RenameConversation,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = ai_assistant_service.rename_conversation(db, conversation_id, data.title)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"title": data.title}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = ai_assistant_service.delete_conversation(db, conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "Conversation deleted"}


# ---------- Logs ----------

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