from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.database import User
from src.models.agent_models import AgentSession, AgentMessage, AgentProvider, AgentFile
from src.middleware.auth_middleware import get_current_user
from src.services.agent_service import run_agent_turn
from src.services.file_service import (
    list_directory, read_file, write_file, edit_file,
    search_files, run_command, get_file_info, create_directory, delete_file
)

router = APIRouter(prefix="/agent", tags=["Agent"])


class ProviderCreate(BaseModel):
    name: str
    provider_type: str
    api_url: str
    api_key: Optional[str] = None
    model: str
    config: Optional[dict] = None


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    is_active: Optional[bool] = None
    config: Optional[dict] = None


class SessionCreate(BaseModel):
    title: Optional[str] = "New Session"
    mode: str = "plan"
    project_path: str = "/www"
    provider_id: Optional[str] = None
    system_prompt: Optional[str] = None


class MessageSend(BaseModel):
    message: str


class FileWrite(BaseModel):
    path: str
    content: str


class FileEdit(BaseModel):
    path: str
    old_text: str
    new_text: str


class CommandRun(BaseModel):
    command: str
    cwd: str = "/www"
    timeout: int = 30


class SearchQuery(BaseModel):
    path: str
    pattern: str
    file_pattern: str = "*"
    max_results: int = 30


# ============= Providers =============

@router.get("/providers")
async def list_providers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    providers = db.query(AgentProvider).filter_by(user_id=current_user.id).all()
    return [{
        "id": p.id,
        "name": p.name,
        "provider_type": p.provider_type,
        "api_url": p.api_url,
        "model": p.model,
        "is_active": p.is_active,
        "has_key": bool(p.api_key),
        "created_at": p.created_at.isoformat() if p.created_at else None
    } for p in providers]


@router.post("/providers")
async def create_provider(
    data: ProviderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    provider = AgentProvider(
        user_id=current_user.id,
        name=data.name,
        provider_type=data.provider_type,
        api_url=data.api_url,
        api_key=data.api_key,
        model=data.model,
        config=data.config
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return {"success": True, "id": provider.id}


@router.put("/providers/{provider_id}")
async def update_provider(
    provider_id: str,
    data: ProviderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    provider = db.query(AgentProvider).filter_by(id=provider_id, user_id=current_user.id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    if data.name is not None:
        provider.name = data.name
    if data.api_url is not None:
        provider.api_url = data.api_url
    if data.api_key is not None:
        provider.api_key = data.api_key
    if data.model is not None:
        provider.model = data.model
    if data.is_active is not None:
        provider.is_active = data.is_active
    if data.config is not None:
        provider.config = data.config

    db.commit()
    return {"success": True}


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    provider = db.query(AgentProvider).filter_by(id=provider_id, user_id=current_user.id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    db.delete(provider)
    db.commit()
    return {"success": True}


@router.post("/providers/{provider_id}/test")
async def test_provider(
    provider_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    provider = db.query(AgentProvider).filter_by(id=provider_id, user_id=current_user.id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    from src.services.agent_service import AgentService
    agent = AgentService(provider)
    result = agent.chat([{"role": "user", "content": "Say 'connected' in one word."}], max_tokens=10)
    return result


# ============= Sessions =============

@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    sessions = db.query(AgentSession).filter_by(user_id=current_user.id).order_by(AgentSession.updated_at.desc()).all()
    return [{
        "id": s.id,
        "title": s.title,
        "mode": s.mode,
        "project_path": s.project_path,
        "provider_id": s.provider_id,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None
    } for s in sessions]


@router.post("/sessions")
async def create_session(
    data: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    session = AgentSession(
        user_id=current_user.id,
        title=data.title,
        mode=data.mode,
        project_path=data.project_path,
        provider_id=data.provider_id,
        system_prompt=data.system_prompt
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"success": True, "id": session.id, "mode": session.mode}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    session = db.query(AgentSession).filter_by(id=session_id, user_id=current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = db.query(AgentMessage).filter_by(session_id=session.id).order_by(AgentMessage.created_at).all()

    return {
        "id": session.id,
        "title": session.title,
        "mode": session.mode,
        "project_path": session.project_path,
        "provider_id": session.provider_id,
        "messages": [{
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "tool_calls": m.tool_calls,
            "tool_result": m.tool_result,
            "tokens_used": m.tokens_used,
            "created_at": m.created_at.isoformat() if m.created_at else None
        } for m in messages],
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    session = db.query(AgentSession).filter_by(id=session_id, user_id=current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db.query(AgentMessage).filter_by(session_id=session.id).delete()
    db.query(AgentFile).filter_by(session_id=session.id).delete()
    db.delete(session)
    db.commit()
    return {"success": True}


@router.put("/sessions/{session_id}/mode")
async def switch_mode(
    session_id: str,
    mode: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    session = db.query(AgentSession).filter_by(id=session_id, user_id=current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if mode not in ("plan", "build"):
        raise HTTPException(status_code=400, detail="Mode must be 'plan' or 'build'")
    session.mode = mode
    db.commit()
    return {"success": True, "mode": mode}


# ============= Chat =============

@router.post("/sessions/{session_id}/chat")
async def chat(
    session_id: str,
    data: MessageSend,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    if session_id == "new":
        session = AgentSession(
            user_id=current_user.id,
            title=data.message[:80] if data.message else "New Session",
            mode="plan",
            project_path="/www"
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    else:
        session = db.query(AgentSession).filter_by(id=session_id, user_id=current_user.id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

    result = run_agent_turn(session, data.message, db)
    result["session_id"] = session.id
    return result


# ============= File Operations =============

@router.post("/files/list")
async def api_list_files(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    path = data.get("path", "/www")
    max_depth = data.get("max_depth", 2)
    return list_directory(path, max_depth)


@router.post("/files/read")
async def api_read_file(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    path = data.get("path", "")
    offset = data.get("offset", 0)
    limit = data.get("limit", 500)
    return read_file(path, offset, limit)


@router.post("/files/write")
async def api_write_file(data: FileWrite, current_user: User = Depends(get_current_user)):
    return write_file(data.path, data.content)


@router.post("/files/edit")
async def api_edit_file(data: FileEdit, current_user: User = Depends(get_current_user)):
    return edit_file(data.path, data.old_text, data.new_text)


@router.post("/files/search")
async def api_search_files(data: SearchQuery, current_user: User = Depends(get_current_user)):
    return search_files(data.path, data.pattern, data.file_pattern, data.max_results)


@router.post("/files/info")
async def api_file_info(data: Dict[str, str], current_user: User = Depends(get_current_user)):
    return get_file_info(data.get("path", ""))


@router.post("/files/mkdir")
async def api_mkdir(data: Dict[str, str], current_user: User = Depends(get_current_user)):
    return create_directory(data.get("path", ""))


@router.post("/files/delete")
async def api_delete_file(data: Dict[str, str], current_user: User = Depends(get_current_user)):
    return delete_file(data.get("path", ""))


@router.post("/command/run")
async def api_run_command(data: CommandRun, current_user: User = Depends(get_current_user)):
    return run_command(data.command, data.cwd, data.timeout)


# ============= Stats =============

@router.get("/stats")
async def agent_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    sessions = db.query(AgentSession).filter_by(user_id=current_user.id).count()
    providers = db.query(AgentProvider).filter_by(user_id=current_user.id).count()
    messages = db.query(AgentMessage).join(AgentSession).filter(AgentSession.user_id == current_user.id).count()

    total_tokens = db.query(AgentMessage.tokens_used).join(AgentSession).filter(
        AgentSession.user_id == current_user.id,
        AgentMessage.tokens_used.isnot(None)
    ).all()
    total_tokens = sum(t[0] or 0 for t in total_tokens)

    return {
        "total_sessions": sessions,
        "total_providers": providers,
        "total_messages": messages,
        "total_tokens": total_tokens
    }
