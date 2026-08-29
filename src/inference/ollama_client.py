import httpx
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.config import settings


class OllamaClient:
    def __init__(self):
        self.base_url = settings.inference.ollama.base_url
        self.timeout = settings.inference.ollama.timeout

    async def generate(
        self,
        prompt: str,
        model: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 100,
        stop: Optional[List[str]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "model": model,
                "prompt": prompt,
                "temperature": temperature,
                "top_p": top_p,
                "options": {
                    "num_predict": max_tokens
                },
                "stream": stream
            }

            if system:
                payload["system"] = system
            if stop:
                payload["options"]["stop"] = stop

            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            return response.json()

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 100,
        stop: Optional[List[str]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "top_p": top_p,
                "options": {
                    "num_predict": max_tokens
                },
                "stream": stream
            }

            if stop:
                payload["options"]["stop"] = stop

            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            return response.json()

    async def list_models(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])

    async def get_model_info(self, model: str) -> Optional[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/show",
                    json={"name": model}
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError:
                return None

    async def pull_model_stream(self, model: str):
        async with httpx.AsyncClient(timeout=self.timeout * 10) as client:
            payload = {"name": model, "stream": True}
            async with client.stream(
                "POST",
                f"{self.base_url}/api/pull",
                json=payload
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        yield line

    async def pull_model(self, model: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout * 10) as client:
            payload = {"name": model, "stream": False}
            response = await client.post(f"{self.base_url}/api/pull", json=payload)
            response.raise_for_status()
            return response.json()

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/")
                return response.status_code == 200
        except Exception:
            return False


class LMStudioClient:
    def __init__(self):
        self.base_url = settings.inference.lmstudio.base_url
        self.timeout = settings.inference.lmstudio.timeout

    async def generate(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 100,
        stop: Optional[List[str]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "model": model,
                "prompt": prompt,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
                "stream": stream
            }

            if stop:
                payload["stop"] = stop

            response = await client.post(f"{self.base_url}/v1/completions", json=payload)
            response.raise_for_status()
            return response.json()

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 100,
        stop: Optional[List[str]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
                "stream": stream
            }

            if stop:
                payload["stop"] = stop

            response = await client.post(f"{self.base_url}/v1/chat/completions", json=payload)
            response.raise_for_status()
            return response.json()

    async def list_models(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/v1/models")
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/v1/models")
                return response.status_code == 200
        except Exception:
            return False


def get_inference_client():
    if settings.inference.provider == "ollama":
        return OllamaClient()
    elif settings.inference.provider == "lmstudio":
        return LMStudioClient()
    else:
        return OllamaClient()


ollama_client = OllamaClient()
lmstudio_client = LMStudioClient()
