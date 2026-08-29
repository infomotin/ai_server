import time
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.config import settings
from src.inference.ollama_client import ollama_client, lmstudio_client, get_inference_client
from src.models.schemas import (
    CompletionRequest, ChatCompletionRequest,
    CompletionResponse, ChatCompletionResponse,
    CompletionChoice, CompletionUsage, ChatCompletionChoice, ChatMessage
)
from src.models.database import APIKey
from src.services.usage_service import usage_service


class InferenceService:
    def __init__(self):
        self.provider = settings.inference.provider

    def _count_tokens(self, text: str) -> int:
        return len(text) // 4

    async def complete(
        self,
        request: CompletionRequest,
        api_key: APIKey,
        db: Any
    ) -> CompletionResponse:
        start_time = time.time()

        client = get_inference_client()

        if isinstance(client, type(ollama_client)):
            system_prompt = None
            prompt = request.prompt

            result = await client.generate(
                prompt=prompt,
                model=request.model,
                temperature=request.temperature,
                top_p=request.top_p,
                max_tokens=request.max_tokens,
                stop=request.stop,
                stream=False
            )

            response_text = result.get("response", "")

            if request.echo:
                response_text = prompt + response_text

            prompt_tokens = self._count_tokens(prompt)
            completion_tokens = self._count_tokens(response_text)

        else:
            result = await client.generate(
                prompt=request.prompt,
                model=request.model,
                temperature=request.temperature,
                top_p=request.top_p,
                max_tokens=request.max_tokens,
                stop=request.stop,
                stream=False
            )

            response_text = result["choices"][0]["text"]
            prompt_tokens = result.get("usage", {}).get("prompt_tokens", self._count_tokens(request.prompt))
            completion_tokens = result.get("usage", {}).get("completion_tokens", self._count_tokens(response_text))

        latency_ms = int((time.time() - start_time) * 1000)

        usage_service.log_usage(
            db=db,
            api_key_id=api_key.id,
            model=request.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms
        )

        return CompletionResponse(
            id=f"cmpl-{uuid.uuid4().hex[:8]}",
            created=int(datetime.now().timestamp()),
            model=request.model,
            choices=[CompletionChoice(
                text=response_text,
                index=0,
                finish_reason="stop"
            )],
            usage=CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
        )

    async def chat_complete(
        self,
        request: ChatCompletionRequest,
        api_key: APIKey,
        db: Any
    ) -> ChatCompletionResponse:
        start_time = time.time()

        client = get_inference_client()

        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        if isinstance(client, type(ollama_client)):
            result = await client.chat(
                messages=messages,
                model=request.model,
                temperature=request.temperature,
                top_p=request.top_p,
                max_tokens=request.max_tokens,
                stop=request.stop,
                stream=False
            )

            response_content = result.get("message", {}).get("content", "")
            prompt_tokens = self._count_tokens(str(messages))
            completion_tokens = self._count_tokens(response_content)

        else:
            result = await client.chat(
                messages=messages,
                model=request.model,
                temperature=request.temperature,
                top_p=request.top_p,
                max_tokens=request.max_tokens,
                stop=request.stop,
                stream=False
            )

            response_content = result["choices"][0]["message"]["content"]
            prompt_tokens = result.get("usage", {}).get("prompt_tokens", self._count_tokens(str(messages)))
            completion_tokens = result.get("usage", {}).get("completion_tokens", self._count_tokens(response_content))

        latency_ms = int((time.time() - start_time) * 1000)

        usage_service.log_usage(
            db=db,
            api_key_id=api_key.id,
            model=request.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms
        )

        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(datetime.now().timestamp()),
            model=request.model,
            choices=[ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=response_content),
                finish_reason="stop"
            )],
            usage=CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
        )


inference_service = InferenceService()
