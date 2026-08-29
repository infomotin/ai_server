from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.schemas import UserResponse, UserUpdate
from src.services.user_service import user_service
from src.middleware.auth_middleware import get_current_user
from src.models.database import User

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    if update_data.email and update_data.email != current_user.email:
        if user_service.get_user_by_email(db, update_data.email):
            raise HTTPException(status_code=400, detail="Email already in use")

    if update_data.username and update_data.username != current_user.username:
        if user_service.get_user_by_username(db, update_data.username):
            raise HTTPException(status_code=400, detail="Username already taken")

    updated_user = user_service.update_user(db, current_user, update_data)
    return UserResponse.model_validate(updated_user)


@router.delete("/me", status_code=204)
async def delete_current_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    user_service.delete_user(db, current_user.id)
    return None
