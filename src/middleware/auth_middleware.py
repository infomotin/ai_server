from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.database import User, APIKey
from src.services.api_key_service import api_key_service

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db_session)
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = credentials.credentials
    from src.services.auth import auth_service
    payload = auth_service.decode_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = auth_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db_session)
) -> Optional[User]:
    if not credentials:
        return None

    try:
        token = credentials.credentials
        from src.services.auth import auth_service
        payload = auth_service.decode_token(token)

        if not payload:
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        user = auth_service.get_user_by_id(db, user_id)
        return user if user and user.is_active else None
    except Exception:
        return None


async def get_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db_session)
) -> APIKey:
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Missing API key",
                "type": "authentication_error",
                "code": 401
            }
        )

    token = credentials.credentials
    api_key = api_key_service.validate_key(db, token)

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Invalid API key",
                "type": "authentication_error",
                "code": 401
            }
        )

    return api_key


def require_scope(required_scope: str):
    async def scope_checker(
        api_key: APIKey = Depends(get_api_key),
        db: Session = Depends(get_db_session)
    ) -> APIKey:
        if not api_key_service.check_scope(api_key, required_scope):
            raise HTTPException(
                status_code=403,
                detail={
                    "message": f"API key does not have required scope: {required_scope}",
                    "type": "permission_error",
                    "code": 403
                }
            )
        return api_key

    return scope_checker
