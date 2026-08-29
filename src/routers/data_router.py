from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.schemas import DataSourceResponse, DataSourceUpdate
from src.services.data_service import data_service
from src.middleware.auth_middleware import get_current_user
from src.models.database import User
from src.config import settings

router = APIRouter(prefix="/data", tags=["Data Sources"])


@router.post("", response_model=DataSourceResponse, status_code=201)
async def create_data_source(
    name: str = Form(...),
    source_type: str = Form(...),
    content: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    data = await db
    data_source = data_service.create_data_source(
        db,
        current_user.id,
        {
            "name": name,
            "source_type": source_type,
            "content": content
        }
    )
    return DataSourceResponse.model_validate(data_source)


@router.post("/upload", response_model=DataSourceResponse)
async def upload_file(
    file: UploadFile = File(...),
    name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    if file.size and file.size > settings.data.max_file_size:
        raise HTTPException(status_code=400, detail="File too large")

    content = await file.read()
    file_path, file_size = data_service.save_uploaded_file(content, file.filename, current_user.id)

    data_source = data_service.create_data_source(
        db,
        current_user.id,
        {
            "name": name or file.filename,
            "source_type": "file",
            "file_path": file_path,
            "file_size": file_size,
            "metadata": {"content_type": file.content_type}
        }
    )

    return DataSourceResponse.model_validate(data_source)


@router.get("", response_model=List[DataSourceResponse])
async def list_data_sources(
    source_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    sources = data_service.get_user_data_sources(db, current_user.id, source_type)
    return [DataSourceResponse.model_validate(s) for s in sources]


@router.get("/{source_id}", response_model=DataSourceResponse)
async def get_data_source(
    source_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    source = data_service.get_data_source(db, source_id, current_user.id)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    return DataSourceResponse.model_validate(source)


@router.put("/{source_id}", response_model=DataSourceResponse)
async def update_data_source(
    source_id: str,
    update_data: DataSourceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    source = data_service.get_data_source(db, source_id, current_user.id)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    updated = data_service.update_data_source(db, source, update_data)
    return DataSourceResponse.model_validate(updated)


@router.delete("/{source_id}", status_code=204)
async def delete_data_source(
    source_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    success = data_service.delete_data_source(db, source_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Data source not found")
    return None


@router.post("/{source_id}/process")
async def process_data_source(
    source_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    source = data_service.get_data_source(db, source_id, current_user.id)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    result = data_service.process_data_source(db, source)
    return result
