from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.schemas import UserSettingsResponse, UserSettingsUpdate, ModelSwitchRequest, SuccessResponse
from src.services.user_settings_service import user_settings_service
from src.services.model_service import model_service
from src.middleware.auth_middleware import get_current_user
from src.models.database import User

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_model=UserSettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    settings = user_settings_service.get_or_create_settings(db, current_user.id)
    return UserSettingsResponse.model_validate(settings)


@router.put("", response_model=UserSettingsResponse)
async def update_settings(
    update_data: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    settings = user_settings_service.get_or_create_settings(db, current_user.id)
    updated = user_settings_service.update_settings(db, settings, update_data)
    return UserSettingsResponse.model_validate(updated)


@router.post("/model", response_model=SuccessResponse)
async def switch_default_model(
    model_data: ModelSwitchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    model = model_service.get_model(db, model_data.model)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found or not available")

    settings = user_settings_service.set_default_model(db, current_user.id, model_data.model)
    return SuccessResponse(
        message=f"Default model switched to {model_data.model}",
        data={"default_model": settings.default_model}
    )


@router.get("/model", response_model=SuccessResponse)
async def get_current_model(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    settings = user_settings_service.get_or_create_settings(db, current_user.id)
    return SuccessResponse(
        message="Current default model",
        data={"default_model": settings.default_model}
    )
