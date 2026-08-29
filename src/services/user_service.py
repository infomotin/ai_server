from typing import Optional, List
from sqlalchemy.orm import Session

from src.models.database import User
from src.models.schemas import UserCreate, UserUpdate
from src.services.auth import auth_service


class UserService:
    def create_user(self, db: Session, user_data: UserCreate) -> User:
        return auth_service.create_user(
            db,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password
        )

    def get_user_by_id(self, db: Session, user_id: str) -> Optional[User]:
        return auth_service.get_user_by_id(db, user_id)

    def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        return auth_service.get_user_by_email(db, email)

    def get_user_by_username(self, db: Session, username: str) -> Optional[User]:
        return auth_service.get_user_by_username(db, username)

    def update_user(self, db: Session, user: User, update_data: UserUpdate) -> User:
        if update_data.username is not None:
            user.username = update_data.username
        if update_data.email is not None:
            user.email = update_data.email

        db.commit()
        db.refresh(user)
        return user

    def delete_user(self, db: Session, user_id: str) -> bool:
        user = self.get_user_by_id(db, user_id)
        if not user:
            return False

        db.delete(user)
        db.commit()
        return True

    def list_users(self, db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        return db.query(User).offset(skip).limit(limit).all()


user_service = UserService()
