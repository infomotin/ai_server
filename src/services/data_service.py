import os
import uuid
from typing import List, Optional, BinaryIO
from sqlalchemy.orm import Session
from datetime import datetime

from src.models.database import DataSource
from src.models.schemas import DataSourceCreate, DataSourceUpdate
from src.config import settings


class DataService:
    def __init__(self):
        os.makedirs(settings.data.upload_dir, exist_ok=True)

    def create_data_source(self, db: Session, user_id: str, data: DataSourceCreate) -> DataSource:
        source = DataSource(
            user_id=user_id,
            name=data.name,
            source_type=data.source_type,
            content=data.content,
            metadata=data.metadata
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        return source

    def get_data_source(self, db: Session, source_id: str, user_id: str) -> Optional[DataSource]:
        return db.query(DataSource).filter(
            DataSource.id == source_id,
            DataSource.user_id == user_id
        ).first()

    def get_user_data_sources(self, db: Session, user_id: str, source_type: Optional[str] = None) -> List[DataSource]:
        query = db.query(DataSource).filter(DataSource.user_id == user_id)
        if source_type:
            query = query.filter(DataSource.source_type == source_type)
        return query.order_by(DataSource.created_at.desc()).all()

    def update_data_source(self, db: Session, source: DataSource, update_data: DataSourceUpdate) -> DataSource:
        if update_data.name is not None:
            source.name = update_data.name
        if update_data.content is not None:
            source.content = update_data.content
        if update_data.is_processed is not None:
            source.is_processed = update_data.is_processed

        source.updated_at = datetime.now()
        db.commit()
        db.refresh(source)
        return source

    def delete_data_source(self, db: Session, source_id: str, user_id: str) -> bool:
        source = self.get_data_source(db, source_id, user_id)
        if not source:
            return False

        if source.file_path and os.path.exists(source.file_path):
            try:
                os.remove(source.file_path)
            except OSError:
                pass

        db.delete(source)
        db.commit()
        return True

    def save_uploaded_file(self, file_content: bytes, filename: str, user_id: str) -> tuple[str, int]:
        file_ext = os.path.splitext(filename)[1]
        unique_filename = f"{user_id}_{uuid.uuid4().hex}{file_ext}"
        file_path = os.path.join(settings.data.upload_dir, unique_filename)

        with open(file_path, "wb") as f:
            f.write(file_content)

        return file_path, len(file_content)

    def read_file_content(self, file_path: str, max_size: int = 10485760) -> Optional[str]:
        if not os.path.exists(file_path):
            return None

        file_size = os.path.getsize(file_path)
        if file_size > max_size:
            return None

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def process_data_source(self, db: Session, source: DataSource) -> dict:
        if source.source_type == "file" and source.file_path:
            content = self.read_file_content(source.file_path)
            if content:
                source.content = content[:100000]
                source.is_processed = True
                source.extra_metadata = source.extra_metadata or {}
                source.extra_metadata["char_count"] = len(content)
                db.commit()
                return {"status": "success", "chars_processed": len(content)}

        source.is_processed = True
        db.commit()
        return {"status": "success"}


data_service = DataService()
