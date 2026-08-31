import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings, ensure_directories
from src.models.engine import create_tables, init_engine, init_async_engine
from src.routers import (
    auth_router,
    users_router,
    keys_router,
    completions_router,
    models_router,
    skills_router,
    data_router,
    settings_router,
    skill_chat_router,
    management_router,
    model_builder_router,
    firewall_router,
    database_router,
    ai_assistant_router,
    integrations_router,
    agent_router,
    mcp_router,
    training_router,
    camera_router,
    rbac_router,
    monitoring_router
)

logging.basicConfig(
    level=getattr(logging, settings.logging.level),
    format=settings.logging.format
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting OpenLocalAI Server...")
    logger.info(f"Binding to {settings.app.host}:{settings.app.port}")

    ensure_directories()

    init_engine()
    create_tables()
    init_async_engine()
    logger.info("Database initialized")

    from src.services.model_service import model_service
    from src.models.engine import session_factory
    db = session_factory()
    try:
        model_service.init_default_models(db)
        logger.info("Default models initialized")
    finally:
        db.close()

    yield

    logger.info("Shutting down OpenLocalAI Server...")


app = FastAPI(
    title=settings.app.name,
    description="Self-hosted AI API server with OpenAI-compatible endpoints",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "server_error",
                "code": 500
            }
        }
    )


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(keys_router)
app.include_router(completions_router)
app.include_router(models_router)
app.include_router(skills_router)
app.include_router(data_router)
app.include_router(settings_router)
app.include_router(skill_chat_router)
app.include_router(management_router)
app.include_router(model_builder_router)
app.include_router(firewall_router)
app.include_router(database_router)
app.include_router(ai_assistant_router)
app.include_router(integrations_router)
app.include_router(agent_router)
app.include_router(mcp_router)
app.include_router(training_router.router)
app.include_router(camera_router.router)
app.include_router(rbac_router)
app.include_router(monitoring_router.router)


@app.get("/")
async def root():
    return {
        "name": settings.app.name,
        "version": "1.0.0",
        "status": "running",
        "api_docs": "/docs",
        "public_ip": settings.app.host,
        "port": settings.app.port
    }


@app.get("/health")
async def health_check():
    from src.inference.ollama_client import ollama_client

    ollama_healthy = await ollama_client.check_health()

    return {
        "status": "healthy" if ollama_healthy else "degraded",
        "services": {
            "api": "up",
            "ollama": "up" if ollama_healthy else "down"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.debug
    )
