from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.schemas import ChatCompletionRequest, ChatCompletionResponse, ChatWithSkillRequest
from src.services.inference_service import inference_service
from src.services.skill_service import skill_service
from src.services.user_settings_service import user_settings_service
from src.services.model_service import model_service
from src.middleware.auth_middleware import get_api_key, require_scope
from src.middleware.rate_limiter import check_api_key_rate_limit
from src.models.database import APIKey

router = APIRouter(prefix="/v1", tags=["Skill-Enhanced Completions"])


@router.post("/chat/completions/skill", response_model=ChatCompletionResponse)
async def chat_with_skill(
    request: ChatWithSkillRequest,
    api_key: APIKey = Depends(require_scope("chat/completions")),
    db: Session = Depends(get_db_session)
):
    allowed, remaining = check_api_key_rate_limit(api_key.id, api_key.rate_limit)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"message": "Rate limit exceeded", "type": "rate_limit_error", "code": 429}
        )

    skill = None
    if request.skill_id:
        skill = skill_service.get_skill(db, request.skill_id, api_key.user_id)
    elif request.skill_name:
        skill = skill_service.get_skill_by_name(db, request.skill_name, api_key.user_id)

    if request.skill_id or request.skill_name:
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        if not skill.is_active:
            raise HTTPException(status_code=400, detail="Skill is not active")

    model = request.model
    if not model:
        settings = user_settings_service.get_or_create_settings(db, api_key.user_id)
        model = settings.default_model

    model_info = model_service.get_model(db, model)
    if model_info and not model_info.is_downloaded:
        raise HTTPException(
            status_code=503,
            detail={"message": f"Model {model} is not downloaded", "type": "model_not_ready"}
        )

    messages_dict = [{"role": m.role, "content": m.content} for m in request.messages]

    if skill:
        messages_dict = skill_service.apply_skill_to_messages(skill, messages_dict)

    from src.models.schemas import ChatMessage
    messages = [ChatMessage(role=m["role"], content=m["content"]) for m in messages_dict]

    from src.models.schemas import ChatCompletionRequest as CCR
    chat_request = CCR(
        model=model,
        messages=messages,
        max_tokens=request.max_tokens,
        temperature=request.temperature
    )

    try:
        response = await inference_service.chat_complete(chat_request, api_key, db)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"message": f"Inference failed: {str(e)}", "type": "server_error"}
        )
