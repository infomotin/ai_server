from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.schemas import UserCreate, UserLogin, UserResponse, TokenResponse
from src.services.auth import auth_service
from src.services.user_service import user_service
from src.middleware.auth_middleware import get_current_user
from src.models.database import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(user_data: UserCreate, db: Session = Depends(get_db_session)):
    if user_service.get_user_by_email(db, user_data.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    if user_service.get_user_by_username(db, user_data.username):
        raise HTTPException(status_code=400, detail="Username already taken")

    user = user_service.create_user(db, user_data)

    token = auth_service.create_access_token(user.id)

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: Session = Depends(get_db_session)):
    user = auth_service.authenticate_user(db, login_data.email, login_data.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    auth_service.update_last_login(db, user)

    token = auth_service.create_access_token(user.id)

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
