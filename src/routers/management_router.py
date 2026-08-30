import os
import time
import uuid
from datetime import datetime, timedelta
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


# ---------------------------------------------------------------------------
# Advanced / live endpoints
# ---------------------------------------------------------------------------

_METRICS_HISTORY: list = []  # rolling samples for the dashboard chart
_METRICS_MAX = 120           # ~ last 20 minutes at 10s cadence


def _record_sample(sample: dict) -> None:
    _METRICS_HISTORY.append(sample)
    if len(_METRICS_HISTORY) > _METRICS_MAX:
        del _METRICS_HISTORY[: len(_METRICS_HISTORY) - _METRICS_MAX]


@router.get("/live-metrics")
async def get_live_metrics(
    current_user: User = Depends(get_current_user)
):
    """System resources + a snapshot of recent request activity + GPU info."""
    from src.services.usage_service import usage_service
    from src.models.engine import session_factory
    from src.models.database import UsageLog, APIKey

    if session_factory is None:
        from src.models.engine import init_engine
        init_engine()

    resources = management_service.get_system_resources()

    db = session_factory()
    try:
        key_ids = [k.id for k in db.query(APIKey).filter(APIKey.user_id == current_user.id).all()]
        recent: list = []
        if key_ids:
            recent = usage_service.get_recent_usage(db, key_ids[0], limit=200)
        cutoff = datetime.utcnow() - timedelta(seconds=60)
        request_rate = sum(1 for r in recent if r.created_at and r.created_at >= cutoff)
        total_tokens = sum((r.total_tokens or 0) for r in recent)
        by_model: dict = {}
        for r in recent:
            m = r.model or "unknown"
            by_model[m] = by_model.get(m, 0) + 1
    finally:
        db.close()

    gpu = management_service.get_gpu_info() if hasattr(management_service, "get_gpu_info") else {"available": False}

    sample = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "cpu": resources.get("cpu_percent", 0),
        "mem": resources.get("memory_percent", 0),
        "disk": resources.get("disk_percent", 0),
        "active_tasks": resources.get("active_tasks", 0),
        "req_per_min": request_rate,
    }
    _record_sample(sample)

    return {
        "current": sample,
        "history": list(_METRICS_HISTORY),
        "total_tokens_recent": total_tokens,
        "by_model": by_model,
        "gpu": gpu,
    }


@router.post("/knowledge-bases/{kb_id}/search")
async def search_knowledge_base(
    kb_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Lightweight KB introspection. Performs keyword matching on chunked text
    stored on disk next to the KB's file_path. Returns up to ``top_k`` matches.
    """
    from src.models.database import KnowledgeBase
    import os, re

    query = (payload or {}).get("query", "").strip()
    top_k = max(1, min(20, int((payload or {}).get("top_k", 5))))
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    kb = db.query(KnowledgeBase).filter(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == current_user.id,
    ).first()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # Try to find an adjacent chunks file or fall back to a saved content file.
    candidates: list = []
    for p in [kb.file_path]:
        if p and os.path.isfile(p):
            with open(p, "r", errors="ignore") as f:
                txt = f.read()
            for chunk in management_service._chunk_text(txt):
                candidates.append({"source": os.path.basename(p), "text": chunk})

    if not candidates and kb.content_text:
        for chunk in management_service._chunk_text(kb.content_text):
            candidates.append({"source": kb.name, "text": chunk})

    if not candidates:
        return {"results": [], "warning": "No extractable text on disk for this KB."}

    tokens = [t for t in re.split(r"\W+", query.lower()) if len(t) > 1]
    if not tokens:
        return {"results": []}

    scored = []
    for c in candidates:
        low = c["text"].lower()
        score = sum(low.count(t) for t in tokens)
        if score > 0:
            snippet = c["text"][:600]
            scored.append({"score": score, "source": c["source"], "snippet": snippet})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"results": scored[:top_k]}


@router.post("/benchmark")
async def benchmark_model(
    payload: dict,
    current_user: User = Depends(get_current_user)
):
    """Run a quick latency / tokens-per-second benchmark on a model."""
    from src.inference.ollama_client import ollama_client
    import time

    model_id = (payload or {}).get("model_id")
    prompt = (payload or {}).get("prompt", "Write a short poem about open source AI in exactly three lines.")
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id required")

    started = time.time()
    try:
        text, usage = await ollama_client.generate(
            model=model_id,
            prompt=prompt,
            stream=False,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    elapsed = time.time() - started

    completion_tokens = (usage or {}).get("completion_tokens") or 0
    prompt_tokens = (usage or {}).get("prompt_tokens") or 0
    tps = (completion_tokens / elapsed) if elapsed > 0 and completion_tokens else 0.0

    return {
        "model": model_id,
        "elapsed_s": round(elapsed, 3),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tokens_per_second": round(tps, 2),
        "preview": (text or "")[:400],
    }


@router.post("/playground")
async def prompt_playground(
    payload: dict,
    current_user: User = Depends(get_current_user)
):
    """Send a one-off chat completion to a chosen model for testing."""
    from src.inference.ollama_client import ollama_client
    import time

    model_id = (payload or {}).get("model_id")
    messages = (payload or {}).get("messages") or []
    if not model_id or not messages:
        raise HTTPException(status_code=400, detail="model_id and messages required")

    started = time.time()
    try:
        result = await ollama_client.chat(
            model=model_id,
            messages=messages,
            stream=False,
        )
        text = result.get("message", {}).get("content", "")
        usage = result.get("usage", {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    elapsed = time.time() - started

    return {
        "model": model_id,
        "elapsed_s": round(elapsed, 3),
        "content": text or "",
        "usage": usage or {},
    }


@router.get("/activity")
async def get_activity(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Recent API usage / chat activity for the live activity log."""
    from src.services.usage_service import usage_service
    from src.models.database import APIKey
    rows = db.query(APIKey).filter(APIKey.user_id == current_user.id).all()
    key_ids = [k.id for k in rows]
    if not key_ids:
        return []
    recent = usage_service.get_recent_usage(db, key_ids[0], limit=limit)
    return [
        {
            "id": r.id,
            "model": r.model,
            "tokens": r.total_tokens,
            "latency_ms": r.latency_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in recent
    ]


@router.get("/health-check")
async def health_check(
    current_user: User = Depends(get_current_user)
):
    """Probe the Ollama backend and report a structured status."""
    from src.inference.ollama_client import ollama_client
    started = time.time()
    try:
        ok = await ollama_client.check_health()
        latency_ms = int((time.time() - started) * 1000)
        return {
            "ollama_reachable": bool(ok),
            "latency_ms": latency_ms,
            "base_url": getattr(ollama_client, "base_url", ""),
            "checked_at": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        return {
            "ollama_reachable": False,
            "error": str(e),
            "latency_ms": -1,
            "checked_at": datetime.utcnow().isoformat() + "Z",
        }


@router.put("/resources/allocation")
async def update_resource_allocation(
    data: ResourceAllocationUpdate,
    current_user: User = Depends(get_current_user)
):
    return SuccessResponse(
        message="Resource allocation updated",
        data={"max_concurrent_tasks": data.max_concurrent_tasks, "max_memory_percent": data.max_memory_percent}
    )
