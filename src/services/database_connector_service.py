import json
import csv
import io
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect, create_engine

from src.models.database import DataSource


SUPPORTED_DBS = {
    "mysql": {
        "name": "MySQL",
        "icon": "fas fa-dolphin",
        "color": "blue",
        "default_port": 3306,
        "driver": "pymysql",
        "scheme": "mysql+pymysql"
    },
    "postgresql": {
        "name": "PostgreSQL",
        "icon": "fas fa-elephant",
        "color": "indigo",
        "default_port": 5432,
        "driver": "psycopg2",
        "scheme": "postgresql+psycopg2"
    },
    "mssql": {
        "name": "MS SQL Server",
        "icon": "fas fa-server",
        "color": "red",
        "default_port": 1433,
        "driver": "pymssql",
        "scheme": "mssql+pymssql"
    },
    "oracle": {
        "name": "Oracle",
        "icon": "fas fa-database",
        "color": "amber",
        "default_port": 1521,
        "driver": "cx_Oracle",
        "scheme": "oracle+cx_oracle"
    },
    "sqlite": {
        "name": "SQLite",
        "icon": "fas fa-file-code",
        "color": "green",
        "default_port": None,
        "driver": "sqlite3",
        "scheme": "sqlite"
    }
}


class DatabaseConnector:
    def get_supported_dbs(self) -> Dict[str, Any]:
        return SUPPORTED_DBS

    def build_connection_url(self, db_type: str, host: str = None, port: int = None,
                             database: str = None, username: str = None, password: str = None,
                             file_path: str = None) -> str:
        config = SUPPORTED_DBS.get(db_type)
        if not config:
            raise ValueError(f"Unsupported database type: {db_type}")

        if db_type == "sqlite":
            if not file_path:
                raise ValueError("SQLite requires a file path")
            return f"sqlite:///{file_path}"

        if not all([host, database, username, password]):
            raise ValueError("Host, database, username, and password are required")

        port = port or config["default_port"]
        port_str = f":{port}" if port else ""

        if db_type == "mssql":
            return f"{config['scheme']}://{username}:{password}@{host}{port_str}/{database}?driver=ODBC+Driver+17+for+SQL+Server"

        return f"{config['scheme']}://{username}:{password}@{host}{port_str}/{database}"

    def test_connection(self, db_type: str, host: str = None, port: int = None,
                        database: str = None, username: str = None, password: str = None,
                        file_path: str = None) -> Dict[str, Any]:
        try:
            url = self.build_connection_url(db_type, host, port, database, username, password, file_path)
            
            connect_args = {}
            if db_type == "sqlite":
                connect_args = {}
            elif db_type == "mysql":
                connect_args = {"connect_timeout": 10}
            elif db_type == "postgresql":
                connect_args = {"connect_timeout": 10}
            elif db_type == "mssql":
                connect_args = {"timeout": 10}
            
            engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)

            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()

            engine.dispose()
            return {"success": True, "message": "Connection successful"}
        except ImportError as e:
            driver = SUPPORTED_DBS.get(db_type, {}).get("driver", "unknown")
            return {"success": False, "message": f"Missing driver: {driver}. Install with: pip install {driver}"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}

    def get_databases(self, db_type: str, host: str = None, port: int = None,
                      username: str = None, password: str = None) -> List[str]:
        try:
            config = SUPPORTED_DBS.get(db_type)
            if not config or not config["default_port"]:
                return []

            port = port or config["default_port"]

            if db_type == "mysql":
                url = f"{config['scheme']}://{username}:{password}@{host}:{port}/"
                engine = create_engine(url)
                with engine.connect() as conn:
                    result = conn.execute(text("SHOW DATABASES"))
                    return [row[0] for row in result]
            elif db_type == "postgresql":
                url = f"{config['scheme']}://{username}:{password}@{host}:{port}/postgres"
                engine = create_engine(url)
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT datname FROM pg_database WHERE datistemplate = false"))
                    return [row[0] for row in result]
            elif db_type == "mssql":
                url = f"{config['scheme']}://{username}:{password}@{host}:{port}/master?driver=ODBC+Driver+17+for+SQL+Server"
                engine = create_engine(url)
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT name FROM sys.databases"))
                    return [row[0] for row in result]
            return []
        except Exception as e:
            print(f"Error listing databases: {e}")
            return []

    def get_tables(self, connection_url: str) -> List[Dict[str, Any]]:
        try:
            engine = create_engine(connection_url, pool_pre_ping=True)
            inspector = inspect(engine)

            tables = []
            for table_name in inspector.get_table_names():
                columns = inspector.get_columns(table_name)
                pk_cols = inspector.get_pk_constraint(table_name)
                indexes = inspector.get_indexes(table_name)

                table_info = {
                    "name": table_name,
                    "columns": [
                        {
                            "name": col["name"],
                            "type": str(col["type"]),
                            "nullable": col.get("nullable", True),
                            "primary_key": col["name"] in (pk_cols.get("constrained_columns", []) if pk_cols else [])
                        }
                        for col in columns
                    ],
                    "column_count": len(columns),
                    "primary_key": pk_cols.get("constrained_columns", []) if pk_cols else [],
                    "indexes": [idx.get("column_names", []) for idx in indexes]
                }
                tables.append(table_info)

            engine.dispose()
            return tables
        except Exception as e:
            print(f"Error listing tables: {e}")
            return []

    def get_table_data(self, connection_url: str, table_name: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        try:
            engine = create_engine(connection_url, pool_pre_ping=True)
            inspector = inspect(engine)

            columns = inspector.get_columns(table_name)
            col_names = [col["name"] for col in columns]

            with engine.connect() as conn:
                count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                total_rows = count_result.scalar()

                result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT {limit} OFFSET {offset}"))
                rows = [dict(zip(col_names, row)) for row in result]

            engine.dispose()
            return {
                "columns": col_names,
                "rows": rows,
                "total_rows": total_rows,
                "limit": limit,
                "offset": offset
            }
        except Exception as e:
            print(f"Error reading table: {e}")
            return {"columns": [], "rows": [], "total_rows": 0, "error": str(e)[:200]}

    def export_table_to_training_format(self, connection_url: str, table_name: str,
                                        format_type: str = "json", limit: int = 10000,
                                        text_columns: List[str] = None,
                                        question_column: str = None,
                                        answer_column: str = None) -> Dict[str, Any]:
        try:
            engine = create_engine(connection_url, pool_pre_ping=True)
            inspector = inspect(engine)

            columns = inspector.get_columns(table_name)
            col_names = [col["name"] for col in columns]

            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT {limit}"))
                rows = [dict(zip(col_names, row)) for row in result]

            if not rows:
                return {"error": "No data found", "total_rows": 0}

            training_data = []

            if question_column and answer_column and question_column in col_names and answer_column in col_names:
                for row in rows:
                    q = str(row.get(question_column, "")).strip()
                    a = str(row.get(answer_column, "")).strip()
                    if q and a:
                        training_data.append({"question": q, "answer": a, "source": f"{table_name}"})
            elif text_columns:
                valid_cols = [c for c in text_columns if c in col_names]
                for row in rows:
                    text_parts = []
                    for col in valid_cols:
                        val = str(row.get(col, "")).strip()
                        if val:
                            text_parts.append(f"{col}: {val}")
                    if text_parts:
                        training_data.append({"text": " | ".join(text_parts), "source": f"{table_name}", "metadata": row})
            else:
                for row in rows:
                    parts = []
                    for col in col_names:
                        val = str(row.get(col, "")).strip()
                        if val and val != "None":
                            parts.append(f"{col}: {val}")
                    if parts:
                        full_text = ". ".join(parts)
                        training_data.append({
                            "text": full_text,
                            "source": f"{table_name}",
                            "metadata": row
                        })

            engine.dispose()

            output = ""
            if format_type == "json":
                output = json.dumps(training_data, indent=2, default=str, ensure_ascii=False)
            elif format_type == "csv":
                if training_data:
                    if "text" in training_data[0]:
                        writer = io.StringIO()
                        csv_writer = csv.writer(writer)
                        csv_writer.writerow(["text", "source"])
                        for item in training_data:
                            csv_writer.writerow([item["text"], item["source"]])
                        output = writer.getvalue()
                    elif "question" in training_data[0]:
                        writer = io.StringIO()
                        csv_writer = csv.writer(writer)
                        csv_writer.writerow(["question", "answer", "source"])
                        for item in training_data:
                            csv_writer.writerow([item["question"], item["answer"], item["source"]])
                        output = writer.getvalue()
            elif format_type == "jsonl":
                lines = []
                for item in training_data:
                    lines.append(json.dumps(item, default=str, ensure_ascii=False))
                output = "\n".join(lines)

            char_count = len(output)
            word_count = len(output.split())
            chunk_count = max(1, char_count // 1000)

            return {
                "success": True,
                "format": format_type,
                "total_rows": len(training_data),
                "char_count": char_count,
                "word_count": word_count,
                "chunk_count": chunk_count,
                "estimated_model_size": f"~{max(30, chunk_count * 0.5):.0f}MB",
                "content": output[:50000],
                "preview": training_data[:5] if training_data else []
            }
        except Exception as e:
            return {"error": str(e)[:200]}

    def save_as_data_source(self, db: Session, user_id: str, name: str, content: str,
                            format_type: str, table_name: str, connection_url: str) -> DataSource:
        content_hash = hashlib.md5(content.encode()).hexdigest()
        file_path = f"/www/AI_server/data/db_exports/{user_id}_{table_name}_{content_hash[:8]}.{format_type}"

        import os
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        source = DataSource(
            user_id=user_id,
            name=name,
            source_type=f"database_{format_type}",
            content=content[:100000],
            file_path=file_path,
            file_size=len(content.encode()),
            extra_metadata={
                "table_name": table_name,
                "connection_url": connection_url[:200],
                "format": format_type,
                "exported_at": datetime.utcnow().isoformat()
            },
            is_processed=False
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        return source

    def create_knowledge_from_db(self, db: Session, user_id: str, table_name: str,
                                 content: str, format_type: str) -> Dict[str, Any]:
        from src.models.database import KnowledgeBase

        chunks = []
        chunk_size = 1000
        for i in range(0, len(content), chunk_size):
            chunks.append(content[i:i + chunk_size])

        kb = KnowledgeBase(
            user_id=user_id,
            name=f"DB: {table_name}",
            source_type=f"database_{format_type}",
            content_text=content[:100000],
            chunk_count=len(chunks),
            total_chars=len(content),
            is_active=True
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)

        return {
            "id": kb.id,
            "name": kb.name,
            "chunks": len(chunks),
            "total_chars": len(content)
        }


db_connector = DatabaseConnector()
