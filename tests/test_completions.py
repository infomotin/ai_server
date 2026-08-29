import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from src.models.schemas import CompletionRequest, ChatCompletionRequest, ChatMessage
from src.models.database import APIKey


class TestCompletionRequest:
    def test_completion_request_defaults(self):
        request = CompletionRequest(prompt="Hello, world!")

        assert request.model == "llama3.2:1b"
        assert request.prompt == "Hello, world!"
        assert request.max_tokens == 100
        assert request.temperature == 0.7
        assert request.top_p == 0.9
        assert request.n == 1
        assert request.stream is False
        assert request.echo is False

    def test_completion_request_custom_values(self):
        request = CompletionRequest(
            model="qwen2.5:0.5b",
            prompt="Test prompt",
            max_tokens=50,
            temperature=0.5,
            top_p=0.8,
            n=2
        )

        assert request.model == "qwen2.5:0.5b"
        assert request.max_tokens == 50
        assert request.temperature == 0.5
        assert request.top_p == 0.8
        assert request.n == 2

    def test_completion_request_with_stop(self):
        request = CompletionRequest(
            prompt="Hello",
            stop=["\n", "END"]
        )

        assert request.stop == ["\n", "END"]

    def test_completion_request_model_strips_whitespace(self):
        request = CompletionRequest(
            prompt="Hello",
            model="  llama3.2:1b  "
        )

        assert request.model == "llama3.2:1b"


class TestChatCompletionRequest:
    def test_chat_completion_request_defaults(self):
        messages = [
            ChatMessage(role="user", content="Hello!")
        ]
        request = ChatCompletionRequest(messages=messages)

        assert request.model == "llama3.2:1b"
        assert len(request.messages) == 1
        assert request.max_tokens == 100
        assert request.temperature == 0.7
        assert request.stream is False

    def test_chat_completion_request_with_system_message(self):
        messages = [
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="Hello!")
        ]
        request = ChatCompletionRequest(messages=messages)

        assert len(request.messages) == 2
        assert request.messages[0].role == "system"
        assert request.messages[1].role == "user"

    def test_chat_message_validation(self):
        with pytest.raises(ValueError):
            ChatMessage(role="invalid", content="Test")

    def test_chat_message_valid_roles(self):
        valid_roles = ["system", "user", "assistant"]
        for role in valid_roles:
            msg = ChatMessage(role=role, content="Test")
            assert msg.role == role


class TestAPIKeyModel:
    def test_api_key_default_rate_limit(self):
        api_key = APIKey(
            id="test-id",
            key_hash="test-hash",
            key_prefix="sk-local",
            user_id="user-123",
            name="Test Key"
        )

        assert api_key.rate_limit == 60
        assert api_key.is_active is True

    def test_api_key_scopes_default(self):
        api_key = APIKey(
            id="test-id",
            key_hash="test-hash",
            key_prefix="sk-local",
            user_id="user-123",
            name="Test Key"
        )

        assert api_key.scopes == ["completions", "chat/completions"]
