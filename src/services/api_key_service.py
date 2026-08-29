import secrets
import hashlib
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session

from src.models.database import APIKey, User


class APIKeyService:
    KEY_PREFIX_LENGTH = 8
    KEY_TOTAL_LENGTH = 64

    def generate_key(self) -> str:
        return "sk-local-" + secrets.token_hex(self.KEY_TOTAL_LENGTH // 2)

    def hash_key(self, key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def get_prefix(self, key: str) -> str:
        return key[:self.KEY_PREFIX_LENGTH]

    def create_api_key(
        self,
        db: Session,
        user: User,
        name: str,
        scopes: Optional[List[str]] = None,
        rate_limit: int = 60,
        expires_at: Optional[datetime] = None
    ) -> tuple[APIKey, str]:
        raw_key = self.generate_key()
        key_hash = self.hash_key(raw_key)
        prefix = self.get_prefix(raw_key)

        if scopes is None:
            scopes = ["completions", "chat/completions"]

        api_key = APIKey(
            key_hash=key_hash,
            key_prefix=prefix,
            user_id=user.id,
            name=name,
            scopes=scopes,
            rate_limit=rate_limit,
            expires_at=expires_at
        )

        db.add(api_key)
        db.commit()
        db.refresh(api_key)

        return api_key, raw_key

    def validate_key(self, db: Session, key: str) -> Optional[APIKey]:
        if not key.startswith("sk-local-"):
            return None

        key_hash = self.hash_key(key)
        api_key = db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        ).first()

        if not api_key:
            return None

        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            return None

        api_key.last_used_at = datetime.now(timezone.utc)
        db.commit()

        return api_key

    def get_key_by_id(self, db: Session, key_id: str, user_id: str) -> Optional[APIKey]:
        return db.query(APIKey).filter(
            APIKey.id == key_id,
            APIKey.user_id == user_id
        ).first()

    def get_user_keys(self, db: Session, user_id: str) -> List[APIKey]:
        return db.query(APIKey).filter(APIKey.user_id == user_id).order_by(APIKey.created_at.desc()).all()

    def revoke_key(self, db: Session, key_id: str, user_id: str) -> bool:
        api_key = self.get_key_by_id(db, key_id, user_id)
        if not api_key:
            return False

        api_key.is_active = False
        db.commit()
        return True

    def delete_key(self, db: Session, key_id: str, user_id: str) -> bool:
        api_key = self.get_key_by_id(db, key_id, user_id)
        if not api_key:
            return False

        db.delete(api_key)
        db.commit()
        return True

    def check_scope(self, api_key: APIKey, required_scope: str) -> bool:
        if "*" in api_key.scopes:
            return True
        return required_scope in api_key.scopes


api_key_service = APIKeyService()
