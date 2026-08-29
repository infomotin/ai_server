from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.schemas import (
    CompletionRequest, ChatCompletionRequest,
    CompletionResponse, ChatCompletionResponse
)
from src.services.inference_service import inference_service
from src.services.model_service import model_service
from src.middleware.auth_middleware import get_api_key, require_scope
from src.middleware.rate_limiter import check_api_key_rate_limit
from src.models.database import APIKey
from src.inference.ollama_client import ollama_client

router = APIRouter(tags=["Completions"])


async def verify_model_available(model: str):
    local_models = await ollama_client.list_models()
    available = [m.get("name", "") for m in local_models]
    if model not in available:
        raise HTTPException(
            status_code=503,
            detail={
                "message": f"Model {model} is not available. Pull it with: ollama pull {model}",
                "type": "model_not_ready",
                "code": 503
            }
        )


@router.post("/v1/completions", response_model=CompletionResponse)
async def create_completion(
    request: CompletionRequest,
    api_key: APIKey = Depends(require_scope("completions")),
    db: Session = Depends(get_db_session)
):
    allowed, remaining = check_api_key_rate_limit(api_key.id, api_key.rate_limit)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Rate limit exceeded",
                "type": "rate_limit_error",
                "code": 429
            }
        )

    await verify_model_available(request.model)

    try:
        response = await inference_service.complete(request, api_key, db)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Inference failed: {str(e)}",
                "type": "server_error",
                "code": 500
            }
        )


@router.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def create_chat_completion(
    request: ChatCompletionRequest,
    api_key: APIKey = Depends(require_scope("chat/completions")),
    db: Session = Depends(get_db_session)
):
    allowed, remaining = check_api_key_rate_limit(api_key.id, api_key.rate_limit)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Rate limit exceeded",
                "type": "rate_limit_error",
                "code": 429
            }
        )

    await verify_model_available(request.model)

    try:
        response = await inference_service.chat_complete(request, api_key, db)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Inference failed: {str(e)}",
                "type": "server_error",
                "code": 500
            }
        )
