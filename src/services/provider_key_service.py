"""
Provider Keys Service
Manages external AI provider API keys (OpenAI, Anthropic, NVIDIA, OpenRouter, OpenCode)
and routes inference through the right provider.
"""
import os
import json
import base64
import hashlib
import httpx
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from cryptography.fernet import Fernet

from sqlalchemy.orm import Session
from src.models.database import ProviderKey, ExternalModel
from src.models.engine import session_factory


# ============= Provider Definitions =============
PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "icon": "fas fa-brain",
        "color": "green",
        "base_url": "https://api.openai.com/v1",
        "default_models": [
            {"model_id": "gpt-4o", "description": "Most capable GPT-4 model"},
            {"model_id": "gpt-4o-mini", "description": "Fast, affordable small model"},
            {"model_id": "gpt-4-turbo", "description": "GPT-4 Turbo"},
            {"model_id": "gpt-3.5-turbo", "description": "Fast, inexpensive model"},
            {"model_id": "o1-preview", "description": "Reasoning model"},
            {"model_id": "o1-mini", "description": "Smaller reasoning model"},
        ],
        "key_format": "sk-...",
        "key_placeholder": "sk-proj-...",
        "api_url_help": "https://api.openai.com/v1 (default)",
    },
    "anthropic": {
        "name": "Anthropic (Claude)",
        "icon": "fas fa-robot",
        "color": "orange",
        "base_url": "https://api.anthropic.com/v1",
        "default_models": [
            {"model_id": "claude-3-5-sonnet-20241022", "description": "Most intelligent model"},
            {"model_id": "claude-3-5-haiku-20241022", "description": "Fastest model"},
            {"model_id": "claude-3-opus-20240229", "description": "Powerful model"},
            {"model_id": "claude-3-sonnet-20240229", "description": "Balanced model"},
        ],
        "key_format": "sk-ant-...",
        "key_placeholder": "sk-ant-api03-...",
        "api_url_help": "https://api.anthropic.com/v1 (default)",
    },
    "nvidia": {
        "name": "NVIDIA NIM",
        "icon": "fas fa-microchip",
        "color": "green",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_models": [
            {"model_id": "meta/llama-3.1-70b-instruct", "description": "Llama 3.1 70B"},
            {"model_id": "meta/llama-3.1-8b-instruct", "description": "Llama 3.1 8B"},
            {"model_id": "nvidia/llama-3.1-nemotron-70b-instruct", "description": "Nemotron 70B"},
            {"model_id": "mistralai/mistral-large-2-instruct", "description": "Mistral Large 2"},
            {"model_id": "google/gemma-2-27b-it", "description": "Gemma 2 27B"},
            {"model_id": "microsoft/phi-3.5-mini-instruct", "description": "Phi 3.5 Mini"},
        ],
        "key_format": "nvapi-...",
        "key_placeholder": "nvapi-...",
        "api_url_help": "https://integrate.api.nvidia.com/v1 (default)",
    },
    "openrouter": {
        "name": "OpenRouter",
        "icon": "fas fa-route",
        "color": "purple",
        "base_url": "https://openrouter.ai/api/v1",
        "default_models": [
            {"model_id": "openai/gpt-4o", "description": "GPT-4o via OpenRouter"},
            {"model_id": "anthropic/claude-3.5-sonnet", "description": "Claude 3.5 Sonnet"},
            {"model_id": "google/gemini-pro-1.5", "description": "Gemini Pro 1.5"},
            {"model_id": "meta-llama/llama-3.1-405b-instruct", "description": "Llama 3.1 405B"},
            {"model_id": "qwen/qwen-2.5-72b-instruct", "description": "Qwen 2.5 72B"},
            {"model_id": "deepseek/deepseek-chat", "description": "DeepSeek Chat"},
        ],
        "key_format": "sk-or-...",
        "key_placeholder": "sk-or-v1-...",
        "api_url_help": "https://openrouter.ai/api/v1 (default)",
    },
    "opencode": {
        "name": "OpenCode AI",
        "icon": "fas fa-code",
        "color": "cyan",
        "base_url": "https://opencode.ai/api/v1",
        "default_models": [
            {"model_id": "opencode-gpt-4o", "description": "OpenCode GPT-4o"},
            {"model_id": "opencode-claude-sonnet", "description": "OpenCode Claude"},
            {"model_id": "opencode-llama-70b", "description": "OpenCode Llama 70B"},
        ],
        "key_format": "oc-...",
        "key_placeholder": "oc-...",
        "api_url_help": "https://opencode.ai/api/v1 (default)",
    },
    "groq": {
        "name": "Groq",
        "icon": "fas fa-bolt",
        "color": "red",
        "base_url": "https://api.groq.com/openai/v1",
        "default_models": [
            {"model_id": "llama-3.1-70b-versatile", "description": "Llama 3.1 70B (ultra-fast)"},
            {"model_id": "llama-3.1-8b-instant", "description": "Llama 3.1 8B (fastest)"},
            {"model_id": "mixtral-8x7b-32768", "description": "Mixtral 8x7B"},
            {"model_id": "gemma2-9b-it", "description": "Gemma 2 9B"},
        ],
        "key_format": "gsk_...",
        "key_placeholder": "gsk_...",
        "api_url_help": "https://api.groq.com/openai/v1 (default)",
    },
    "custom": {
        "name": "Custom (OpenAI-compatible)",
        "icon": "fas fa-plug",
        "color": "gray",
        "base_url": "",
        "default_models": [],
        "key_format": "any",
        "key_placeholder": "your-api-key",
        "api_url_help": "https://your-api.example.com/v1",
    },
}


# ============= Encryption =============
def _get_cipher():
    """Get Fernet cipher for encrypting/decrypting API keys."""
    # Derive key from SECRET_KEY env var
    secret = os.environ.get("SECRET_KEY", "openlocalai-default-secret-change-me")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_key(plaintext: str) -> str:
    return _get_cipher().encrypt(plaintext.encode()).decode()


def decrypt_key(ciphertext: str) -> str:
    return _get_cipher().decrypt(ciphertext.encode()).decode()


# ============= Provider Key CRUD =============
class ProviderKeyService:
    """Singleton service for managing external provider API keys."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def list_providers() -> Dict[str, Any]:
        return PROVIDERS

    def list_keys(self, db: Session, user_id: str) -> List[Dict[str, Any]]:
        keys = db.query(ProviderKey).filter(ProviderKey.user_id == user_id).all()
        result = []
        for k in keys:
            models = db.query(ExternalModel).filter(ExternalModel.provider_key_id == k.id).all()
            default_model = next((m for m in models if m.is_default), None)
            result.append({
                "id": k.id,
                "provider": k.provider,
                "name": k.name,
                "api_url": k.api_url,
                "is_active": k.is_active,
                "last_used_at": str(k.last_used_at) if k.last_used_at else None,
                "last_check_at": str(k.last_check_at) if k.last_check_at else None,
                "last_check_ok": k.last_check_ok,
                "model_count": len(models),
                "default_model": default_model.model_id if default_model else None,
                "key_preview": self._preview(k.api_key_enc),
                "created_at": str(k.created_at),
            })
        return result

    def _preview(self, enc_key: str) -> str:
        try:
            plain = decrypt_key(enc_key)
            if len(plain) > 12:
                return plain[:7] + "..." + plain[-4:]
            return plain[:4] + "..."
        except Exception:
            return "***"

    def get_key(self, db: Session, key_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        k = db.query(ProviderKey).filter(ProviderKey.id == key_id, ProviderKey.user_id == user_id).first()
        if not k:
            return None
        models = db.query(ExternalModel).filter(ExternalModel.provider_key_id == k.id).all()
        return {
            "id": k.id,
            "provider": k.provider,
            "name": k.name,
            "api_key": decrypt_key(k.api_key_enc),
            "api_url": k.api_url,
            "is_active": k.is_active,
            "extra_config": json.loads(k.extra_config) if k.extra_config else {},
            "models": [
                {
                    "id": m.id,
                    "model_id": m.model_id,
                    "alias": m.alias,
                    "is_default": m.is_default,
                    "context_window": m.context_window,
                    "description": m.description,
                    "is_active": m.is_active,
                } for m in models
            ],
            "created_at": str(k.created_at),
        }

    def create_key(self, db: Session, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        provider = data.get("provider", "").lower()
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}")
        name = data.get("name", "").strip()
        api_key = data.get("api_key", "").strip()
        if not name or not api_key:
            raise ValueError("Name and api_key are required")
        # Default api_url from provider config
        api_url = data.get("api_url") or PROVIDERS[provider].get("base_url", "")
        key = ProviderKey(
            user_id=user_id,
            provider=provider,
            name=name,
            api_key_enc=encrypt_key(api_key),
            api_url=api_url,
            extra_config=json.dumps(data.get("extra_config", {})) if data.get("extra_config") else None,
        )
        db.add(key)
        db.commit()
        db.refresh(key)
        # Auto-add default models for this provider
        for m in PROVIDERS[provider].get("default_models", []):
            em = ExternalModel(
                provider_key_id=key.id,
                model_id=m["model_id"],
                description=m.get("description"),
            )
            db.add(em)
        db.commit()
        return {"id": key.id, "name": key.name, "provider": key.provider}

    def update_key(self, db: Session, key_id: str, user_id: str, data: Dict[str, Any]) -> bool:
        k = db.query(ProviderKey).filter(ProviderKey.id == key_id, ProviderKey.user_id == user_id).first()
        if not k:
            return False
        if "name" in data:
            k.name = data["name"]
        if "api_key" in data and data["api_key"]:
            k.api_key_enc = encrypt_key(data["api_key"])
        if "api_url" in data:
            k.api_url = data["api_url"] or PROVIDERS[k.provider].get("base_url", "")
        if "is_active" in data:
            k.is_active = bool(data["is_active"])
        if "extra_config" in data:
            k.extra_config = json.dumps(data["extra_config"])
        db.commit()
        return True

    def delete_key(self, db: Session, key_id: str, user_id: str) -> bool:
        k = db.query(ProviderKey).filter(ProviderKey.id == key_id, ProviderKey.user_id == user_id).first()
        if not k:
            return False
        db.delete(k)
        db.commit()
        return True

    def add_model(self, db: Session, key_id: str, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        k = db.query(ProviderKey).filter(ProviderKey.id == key_id, ProviderKey.user_id == user_id).first()
        if not k:
            return None
        model_id = data.get("model_id", "").strip()
        if not model_id:
            raise ValueError("model_id is required")
        em = ExternalModel(
            provider_key_id=k.id,
            model_id=model_id,
            alias=data.get("alias"),
            description=data.get("description"),
            context_window=data.get("context_window"),
        )
        db.add(em)
        db.commit()
        db.refresh(em)
        return {"id": em.id, "model_id": em.model_id}

    def delete_model(self, db: Session, model_id: str, user_id: str) -> bool:
        em = db.query(ExternalModel).filter(ExternalModel.id == model_id).first()
        if not em:
            return False
        # Verify ownership
        k = db.query(ProviderKey).filter(ProviderKey.id == em.provider_key_id, ProviderKey.user_id == user_id).first()
        if not k:
            return False
        db.delete(em)
        db.commit()
        return True

    def set_default_model(self, db: Session, model_id: str, user_id: str) -> bool:
        em = db.query(ExternalModel).filter(ExternalModel.id == model_id).first()
        if not em:
            return False
        k = db.query(ProviderKey).filter(ProviderKey.id == em.provider_key_id, ProviderKey.user_id == user_id).first()
        if not k:
            return False
        # Unset all other defaults for this user
        all_user_keys = db.query(ProviderKey).filter(ProviderKey.user_id == user_id).all()
        for kk in all_user_keys:
            for m in db.query(ExternalModel).filter(ExternalModel.provider_key_id == kk.id).all():
                m.is_default = False
        em.is_default = True
        db.commit()
        return True

    async def test_connection(self, db: Session, key_id: str, user_id: str) -> Dict[str, Any]:
        """Test the provider connection by hitting its /models endpoint."""
        k = db.query(ProviderKey).filter(ProviderKey.id == key_id, ProviderKey.user_id == user_id).first()
        if not k:
            return {"success": False, "error": "Key not found"}
        api_key = decrypt_key(k.api_key_enc)
        base = k.api_url or PROVIDERS[k.provider].get("base_url", "")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Most OpenAI-compatible providers expose /models
                resp = await client.get(f"{base}/models", headers={"Authorization": f"Bearer {api_key}"})
                if resp.status_code == 200:
                    data = resp.json()
                    models = data.get("data", [])
                    k.last_check_at = datetime.utcnow()
                    k.last_check_ok = True
                    db.commit()
                    return {
                        "success": True,
                        "provider": k.provider,
                        "models_available": len(models),
                        "sample_models": [m.get("id", m.get("name", "?")) for m in models[:5]],
                    }
                else:
                    k.last_check_at = datetime.utcnow()
                    k.last_check_ok = False
                    db.commit()
                    return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            k.last_check_at = datetime.utcnow()
            k.last_check_ok = False
            db.commit()
            return {"success": False, "error": str(e)[:200]}

    def fetch_remote_models(self, db: Session, key_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Fetch live list of models from provider's API."""
        k = db.query(ProviderKey).filter(ProviderKey.id == key_id, ProviderKey.user_id == user_id).first()
        if not k:
            return []
        api_key = decrypt_key(k.api_key_enc)
        base = k.api_url or PROVIDERS[k.provider].get("base_url", "")
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(f"{base}/models", headers={"Authorization": f"Bearer {api_key}"})
                if resp.status_code == 200:
                    data = resp.json()
                    return [{"model_id": m.get("id", m.get("name", "?"))} for m in data.get("data", [])]
        except Exception:
            pass
        return []


# ============= Provider Inference Router =============
class ProviderInferenceRouter:
    """Routes inference to the right provider based on the model selected."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_default_model(self, db: Session, user_id: str) -> Optional[Dict[str, Any]]:
        """Get the user's currently selected default external model."""
        em = db.query(ExternalModel).filter(ExternalModel.is_default == True).first()
        if not em:
            return None
        k = db.query(ProviderKey).filter(ProviderKey.id == em.provider_key_id).first()
        if not k or k.user_id != user_id:
            return None
        return {
            "model_id": em.model_id,
            "provider": k.provider,
            "api_key": decrypt_key(k.api_key_enc),
            "api_url": k.api_url or PROVIDERS[k.provider].get("base_url", ""),
        }

    def get_model_by_id(self, db: Session, model_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Resolve a model_id (e.g. gpt-4o) to a provider config."""
        em = db.query(ExternalModel).filter(ExternalModel.model_id == model_id).first()
        if not em:
            return None
        k = db.query(ProviderKey).filter(ProviderKey.id == em.provider_key_id).first()
        if not k or k.user_id != user_id or not k.is_active:
            return None
        return {
            "model_id": em.model_id,
            "provider": k.provider,
            "api_key": decrypt_key(k.api_key_enc),
            "api_url": k.api_url or PROVIDERS[k.provider].get("base_url", ""),
        }

    def list_user_models(self, db: Session, user_id: str) -> List[Dict[str, Any]]:
        """List all external models the user has access to."""
        keys = db.query(ProviderKey).filter(ProviderKey.user_id == user_id, ProviderKey.is_active == True).all()
        result = []
        for k in keys:
            models = db.query(ExternalModel).filter(ExternalModel.provider_key_id == k.id, ExternalModel.is_active == True).all()
            for m in models:
                result.append({
                    "id": m.id,
                    "model_id": m.model_id,
                    "alias": m.alias,
                    "provider": k.provider,
                    "provider_name": PROVIDERS.get(k.provider, {}).get("name", k.provider),
                    "is_default": m.is_default,
                    "description": m.description,
                    "context_window": m.context_window,
                })
        return result

    async def chat(self, db: Session, model_id: str, user_id: str,
                   messages: List[Dict[str, str]], temperature: float = 0.7,
                   max_tokens: int = 1000, stream: bool = False) -> Dict[str, Any]:
        """Route a chat completion to the right provider."""
        config = self.get_model_by_id(db, model_id, user_id) or self.get_default_model(db, user_id)
        if not config:
            return {"error": f"No provider key configured for model '{model_id}'. Add one in /providers."}
        provider = config["provider"]
        api_key = config["api_key"]
        base = config["api_url"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if provider == "anthropic":
            # Anthropic uses x-api-key + separate system
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            system = next((m["content"] for m in messages if m.get("role") == "system"), None)
            user_messages = [m for m in messages if m.get("role") != "system"]
            payload = {
                "model": model_id,
                "messages": user_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if system:
                payload["system"] = system
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(f"{base}/messages", json=payload, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        text = "".join(b.get("text", "") for b in data.get("content", []))
                        return {
                            "success": True,
                            "provider": provider,
                            "content": text,
                            "model": model_id,
                            "usage": data.get("usage", {}),
                        }
                    return {"error": f"Anthropic error: {resp.status_code} {resp.text[:200]}"}
            except Exception as e:
                return {"error": str(e)[:300]}
        else:
            # OpenAI-compatible (OpenAI, NVIDIA, OpenRouter, OpenCode, Groq, custom)
            payload = {
                "model": model_id,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream,
            }
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(f"{base}/chat/completions", json=payload, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            msg = choices[0].get("message", {})
                            return {
                                "success": True,
                                "provider": provider,
                                "content": msg.get("content", ""),
                                "model": model_id,
                                "usage": data.get("usage", {}),
                            }
                        return {"error": "No choices returned"}
                    return {"error": f"{provider} error: {resp.status_code} {resp.text[:200]}"}
            except Exception as e:
                return {"error": str(e)[:300]}


provider_key_service = ProviderKeyService()
provider_inference = ProviderInferenceRouter()
