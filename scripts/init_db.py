#!/usr/bin/env python3
"""
Database initialization script for OpenLocalAI.
Creates all tables and initializes default data.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.engine import create_tables, init_engine, get_db_session
from src.services.model_service import model_service
from src.services.user_service import user_service
from src.services.auth import auth_service
from src.models.schemas import UserCreate


def init_database():
    print("=" * 50)
    print("OpenLocalAI - Database Initialization")
    print("=" * 50)

    print("\n[1] Initializing database engine...")
    init_engine()
    print("✓ Engine initialized")

    print("\n[2] Creating tables...")
    create_tables()
    print("✓ All tables created")

    print("\n[3] Initializing default models...")
    with get_db_session() as db:
        model_service.init_default_models(db)
    print("✓ Default models registered")

    print("\n[4] Creating admin user...")
    with get_db_session() as db:
        existing_admin = user_service.get_user_by_username(db, "admin")
        if not existing_admin:
            admin_data = UserCreate(
                username="admin",
                email="admin@openlocalai.dev",
                password="admin123"
            )
            admin = user_service.create_user(db, admin_data)
            print("✓ Admin user created: admin@openlocalai.dev / admin123")
            print("  WARNING: Change this password in production!")
        else:
            print("✓ Admin user already exists")

    print("\n[5] Ensuring data directories...")
    from src.config import ensure_directories
    ensure_directories()
    print("✓ Directories created")

    print("\n" + "=" * 50)
    print("Database initialization complete!")
    print("=" * 50)
    print("\nNext steps:")
    print("  1. Start Ollama: ollama serve")
    print("  2. Pull a model: ollama pull llama3.2:1b")
    print("  3. Run API server: python -m uvicorn src.main:app --host 0.0.0.0 --port 8000")
    print("  4. Run Web UI: python web/app.py")
    print("  5. Access:")
    print("     - API: http://203.55.176.101:8000")
    print("     - Web: http://203.55.176.101:5000")
    print("     - Docs: http://203.55.176.101:8000/docs")
    print("\n  Admin login: admin@openlocalai.dev / admin123")
    print("=" * 50)


if __name__ == "__main__":
    init_database()
