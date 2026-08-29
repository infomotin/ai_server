from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.schemas import APIKeyCreate, APIKeyResponse, APIKeyWithSecret, UsageStats
from src.services.api_key_service import api_key_service
from src.services.usage_service import usage_service
from src.middleware.auth_middleware import get_current_user
from src.models.database import User

router = APIRouter(prefix="/keys", tags=["API Keys"])


@router.get("", response_model=List[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    keys = api_key_service.get_user_keys(db, current_user.id)
    return [APIKeyResponse.model_validate(key) for key in keys]


@router.post("", response_model=APIKeyWithSecret, status_code=201)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    api_key, secret_key = api_key_service.create_api_key(
        db=db,
        user=current_user,
        name=key_data.name,
        scopes=key_data.scopes,
        rate_limit=key_data.rate_limit or 60,
        expires_at=key_data.expires_at
    )

    return APIKeyWithSecret(
        id=api_key.id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        scopes=api_key.scopes,
        rate_limit=api_key.rate_limit,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        secret_key=secret_key
    )


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    api_key = api_key_service.get_key_by_id(db, key_id, current_user.id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    return APIKeyResponse.model_validate(api_key)


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = api_key_service.revoke_key(db, key_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")
    return None


@router.get("/{key_id}/usage", response_model=UsageStats)
async def get_key_usage(
    key_id: str,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    api_key = api_key_service.get_key_by_id(db, key_id, current_user.id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    usage = usage_service.get_key_usage(db, api_key.id)
    return UsageStats(**usage)
