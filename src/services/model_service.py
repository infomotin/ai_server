from typing import List, Optional
from sqlalchemy.orm import Session
import httpx

from src.models.database import Model
from src.config import settings
from src.inference.ollama_client import ollama_client


DEFAULT_MODELS = [
    {
        "id": "llama3.2:1b",
        "name": "Llama 3.2 1B",
        "provider": "ollama",
        "parameter_count": 1_000_000_000,
        "quantization": "Q4_0"
    },
    {
        "id": "qwen2.5:0.5b",
        "name": "Qwen 2.5 0.5B",
        "provider": "ollama",
        "parameter_count": 500_000_000,
        "quantization": "Q4_0"
    },
    {
        "id": "phi3:mini",
        "name": "Phi-3 Mini",
        "provider": "ollama",
        "parameter_count": 3_800_000_000,
        "quantization": "Q4_0"
    },
    {
        "id": "mistral-nemo",
        "name": "Mistral Nemo",
        "provider": "ollama",
        "parameter_count": 12_000_000_000,
        "quantization": "Q4_0"
    },
    {
        "id": "codellama:3.5",
        "name": "Code Llama 3.5",
        "provider": "ollama",
        "parameter_count": 3_500_000_000,
        "quantization": "Q4_0"
    }
]


class ModelService:
    def __init__(self):
        self.default_model = settings.models.default

    def get_all_models(self, db: Session) -> List[Model]:
        return db.query(Model).all()

    def get_downloaded_models(self, db: Session) -> List[Model]:
        return db.query(Model).filter(Model.is_downloaded == True).all()

    def get_model(self, db: Session, model_id: str) -> Optional[Model]:
        return db.query(Model).filter(Model.id == model_id).first()

    def init_default_models(self, db: Session):
        for model_data in DEFAULT_MODELS:
            existing = self.get_model(db, model_data["id"])
            if not existing:
                model = Model(**model_data)
                db.add(model)
        db.commit()

    async def sync_with_ollama(self, db: Session) -> List[Model]:
        try:
            local_models = await ollama_client.list_models()

            for local_model in local_models:
                model_id = local_model.get("name")
                if not model_id:
                    continue

                model = self.get_model(db, model_id)
                if model:
                    model.is_downloaded = True
                else:
                    model = Model(
                        id=model_id,
                        name=model_id,
                        provider="ollama",
                        is_downloaded=True
                    )
                    db.add(model)

            db.commit()
            return self.get_all_models(db)
        except Exception:
            return self.get_all_models(db)

    async def download_model(self, db: Session, model_id: str) -> dict:
        model = self.get_model(db, model_id)
        if not model:
            model = Model(
                id=model_id,
                name=model_id,
                provider="ollama",
                is_downloaded=False
            )
            db.add(model)
            db.commit()

        try:
            async for status in ollama_client.pull_model_stream(model_id):
                pass

            model.is_downloaded = True
            db.commit()
            return {"status": "success", "model": model_id}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def estimate_model_size(self, model_id: str) -> Optional[int]:
        model_info = next(
            (m for m in DEFAULT_MODELS if m["id"] == model_id),
            None
        )
        if model_info:
            param_count = model_info.get("parameter_count", 0)
            return int(param_count * 0.5)
        return None


model_service = ModelService()
