import os
from pathlib import Path
from typing import List, Optional
import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class AppConfig(BaseModel):
    name: str = "OpenLocalAI"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    secret_key: str = "change-this-in-production"
    cors_origins: List[str] = ["*"]
    allowed_hosts: List[str] = ["*"]


class DatabaseConfig(BaseModel):
    url: str = "mysql+pymysql://aiserver:aiserver@localhost:3306/aiserver"
    echo: bool = False


class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    timeout: int = 300


class LMStudioConfig(BaseModel):
    base_url: str = "http://localhost:1234"
    timeout: int = 300


class InferenceConfig(BaseModel):
    provider: str = "ollama"
    ollama: OllamaConfig = OllamaConfig()
    lmstudio: LMStudioConfig = LMStudioConfig()


class RateLimitingConfig(BaseModel):
    enabled: bool = True
    default_requests_per_minute: int = 60
    burst_size: int = 10


class ModelsConfig(BaseModel):
    default: str = "llama3.2:1b"
    cache_dir: str = "./models"


class DataConfig(BaseModel):
    upload_dir: str = "./data/uploads"
    max_file_size: int = 104857600


class SkillsConfig(BaseModel):
    storage_dir: str = "./data/skills"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class Settings(BaseModel):
    app: AppConfig = AppConfig()
    database: DatabaseConfig = DatabaseConfig()
    inference: InferenceConfig = InferenceConfig()
    rate_limiting: RateLimitingConfig = RateLimitingConfig()
    models: ModelsConfig = ModelsConfig()
    data: DataConfig = DataConfig()
    skills: SkillsConfig = SkillsConfig()
    logging: LoggingConfig = LoggingConfig()


def load_config(config_path: Optional[str] = None) -> Settings:
    if config_path is None:
        config_path = os.environ.get("CONFIG_PATH", "config.yaml")

    path = Path(config_path)
    if path.exists():
        with open(path, "r") as f:
            config_data = yaml.safe_load(f)
        return Settings(**config_data)

    return Settings()


def ensure_directories():
    settings = load_config()
    os.makedirs(settings.data.upload_dir, exist_ok=True)
    os.makedirs(settings.skills.storage_dir, exist_ok=True)
    os.makedirs(settings.models.cache_dir, exist_ok=True)


settings = load_config()
