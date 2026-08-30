from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.database import User
from src.middleware.auth_middleware import get_current_user
from src.services.database_connector_service import db_connector

router = APIRouter(prefix="/database", tags=["Database Connector"])


class DBConnectionTest(BaseModel):
    db_type: str = Field(..., pattern="^(mysql|postgresql|mssql|oracle|sqlite)$")
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    file_path: Optional[str] = None


class DBConnectRequest(BaseModel):
    db_type: str = Field(..., pattern="^(mysql|postgresql|mssql|oracle|sqlite)$")
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    file_path: Optional[str] = None


class DBTableRequest(BaseModel):
    """Connection + table name for single-table operations."""
    db_type: str = Field(..., pattern="^(mysql|postgresql|mssql|oracle|sqlite)$")
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    file_path: Optional[str] = None
    table_name: str


class DBExportRequest(BaseModel):
    connection_url: str
    table_name: str
    format_type: str = Field(default="json", pattern="^(json|csv|jsonl)$")
    limit: int = Field(default=10000, ge=1, le=1000000)
    text_columns: Optional[List[str]] = None
    question_column: Optional[str] = None
    answer_column: Optional[str] = None
    save_as_source: bool = True
    create_knowledge: bool = True


@router.get("/supported")
async def get_supported_databases(current_user: User = Depends(get_current_user)):
    return db_connector.get_supported_dbs()


@router.post("/test")
async def test_connection(
    data: DBConnectionTest,
    current_user: User = Depends(get_current_user)
):
    result = db_connector.test_connection(
        db_type=data.db_type,
        host=data.host,
        port=data.port,
        database=data.database,
        username=data.username,
        password=data.password,
        file_path=data.file_path
    )
    return result


@router.post("/databases")
async def list_databases(
    data: DBConnectRequest,
    current_user: User = Depends(get_current_user)
):
    databases = db_connector.get_databases(
        db_type=data.db_type,
        host=data.host,
        port=data.port,
        username=data.username,
        password=data.password
    )
    return {"databases": databases}


@router.post("/connect")
async def connect_and_list_tables(
    data: DBConnectRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        url = db_connector.build_connection_url(
            db_type=data.db_type,
            host=data.host,
            port=data.port,
            database=data.database,
            username=data.username,
            password=data.password,
            file_path=data.file_path
        )
        # Use lightweight mode (just names + row counts) for fast load on big DBs.
        # Columns are loaded on demand via /table/columns.
        tables = db_connector.get_tables(url, lightweight=True)
        return {"connection_url": url, "tables": tables, "lightweight": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@router.post("/table/columns")
async def get_table_columns_endpoint(
    data: DBTableRequest,
    current_user: User = Depends(get_current_user)
):
    """Lazy-load columns for a single table after connect."""
    try:
        url = db_connector.build_connection_url(
            db_type=data.db_type,
            host=data.host,
            port=data.port,
            database=data.database,
            username=data.username,
            password=data.password,
            file_path=data.file_path
        )
        columns = db_connector.get_table_columns(url, data.table_name)
        return {"table_name": data.table_name, "columns": columns}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


@router.post("/table/row-count")
async def get_table_row_count_endpoint(
    data: DBTableRequest,
    current_user: User = Depends(get_current_user)
):
    """Lazy-load row count for a single table after connect."""
    try:
        url = db_connector.build_connection_url(
            db_type=data.db_type,
            host=data.host,
            port=data.port,
            database=data.database,
            username=data.username,
            password=data.password,
            file_path=data.file_path
        )
        count = db_connector.get_table_row_count(url, data.table_name)
        return {"table_name": data.table_name, "row_count": count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])
async def get_table_data(
    connection_url: str,
    table_name: str,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    from urllib.parse import unquote
    decoded_url = unquote(connection_url)
    data = db_connector.get_table_data(decoded_url, table_name, limit, offset)
    return data


@router.post("/table/data")
async def get_table_data(
    connection_url: str,
    table_name: str,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    from urllib.parse import unquote
    decoded_url = unquote(connection_url)
    data = db_connector.get_table_data(decoded_url, table_name, limit, offset)
    return data


@router.post("/table/export")
async def export_table(
    data: DBExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    result = db_connector.export_table_to_training_format(
        connection_url=data.connection_url,
        table_name=data.table_name,
        format_type=data.format_type,
        limit=data.limit,
        text_columns=data.text_columns,
        question_column=data.question_column,
        answer_column=data.answer_column
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    source_id = None
    kb_id = None

    if data.save_as_source:
        source = db_connector.save_as_data_source(
            db=db,
            user_id=current_user.id,
            name=f"DB: {data.table_name}",
            content=result["content"],
            format_type=data.format_type,
            table_name=data.table_name,
            connection_url=data.connection_url
        )
        source_id = source.id

    if data.create_knowledge and result["content"]:
        kb = db_connector.create_knowledge_from_db(
            db=db,
            user_id=current_user.id,
            table_name=data.table_name,
            content=result["content"],
            format_type=data.format_type
        )
        kb_id = kb["id"]

    return {
        "success": True,
        "format": result["format"],
        "total_rows": result["total_rows"],
        "char_count": result["char_count"],
        "word_count": result["word_count"],
        "chunk_count": result["chunk_count"],
        "estimated_model_size": result["estimated_model_size"],
        "source_id": source_id,
        "knowledge_base_id": kb_id,
        "preview": result["preview"],
        "content_preview": result["content"][:2000]
    }


@router.get("/table/preview")
async def preview_export(
    connection_url: str,
    table_name: str,
    format_type: str = "json",
    limit: int = 10,
    current_user: User = Depends(get_current_user)
):
    from urllib.parse import unquote
    decoded_url = unquote(connection_url)
    result = db_connector.export_table_to_training_format(
        connection_url=decoded_url,
        table_name=table_name,
        format_type=format_type,
        limit=limit
    )
    return result
