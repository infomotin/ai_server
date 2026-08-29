from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

from src.models.database import UserSettings
from src.models.schemas import UserSettingsUpdate


class UserSettingsService:
    def get_or_create_settings(self, db: Session, user_id: str) -> UserSettings:
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not settings:
            settings = UserSettings(user_id=user_id)
            db.add(settings)
            db.commit()
            db.refresh(settings)
        return settings

    def get_settings(self, db: Session, user_id: str) -> Optional[UserSettings]:
        return db.query(UserSettings).filter(UserSettings.user_id == user_id).first()

    def update_settings(self, db: Session, settings: UserSettings, update_data: UserSettingsUpdate) -> UserSettings:
        if update_data.default_model is not None:
            settings.default_model = update_data.default_model
        if update_data.temperature is not None:
            settings.temperature = update_data.temperature
        if update_data.max_tokens is not None:
            settings.max_tokens = update_data.max_tokens
        if update_data.theme is not None:
            settings.theme = update_data.theme

        settings.updated_at = datetime.now()
        db.commit()
        db.refresh(settings)
        return settings

    def set_default_model(self, db: Session, user_id: str, model: str) -> UserSettings:
        settings = self.get_or_create_settings(db, user_id)
        settings.default_model = model
        settings.updated_at = datetime.now()
        db.commit()
        db.refresh(settings)
        return settings


user_settings_service = UserSettingsService()
