import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta, timezone

from src.services.api_key_service import APIKeyService
from src.models.database import APIKey, User


class TestAPIKeyService:
    def setup_method(self):
        self.service = APIKeyService()

    def test_generate_key_format(self):
        key = self.service.generate_key()

        assert key.startswith("sk-local-")
        assert len(key) == 64

    def test_generate_key_unique(self):
        key1 = self.service.generate_key()
        key2 = self.service.generate_key()

        assert key1 != key2

    def test_hash_key_consistent(self):
        key = "sk-local-test123"
        hash1 = self.service.hash_key(key)
        hash2 = self.service.hash_key(key)

        assert hash1 == hash2
        assert len(hash1) == 64

    def test_hash_key_different_inputs(self):
        key1 = "sk-local-test123"
        key2 = "sk-local-test456"

        hash1 = self.service.hash_key(key1)
        hash2 = self.service.hash_key(key2)

        assert hash1 != hash2

    def test_get_prefix(self):
        key = "sk-local-12345678abcdefgh"
        prefix = self.service.get_prefix(key)

        assert prefix == "sk-local"
        assert len(prefix) == 8

    def test_create_api_key(self):
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"

        api_key, secret = self.service.create_api_key(
            db=mock_db,
            user=mock_user,
            name="Test Key",
            rate_limit=100
        )

        assert api_key.name == "Test Key"
        assert api_key.rate_limit == 100
        assert api_key.user_id == "user-123"
        assert secret.startswith("sk-local-")
        assert len(secret) == 64
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_api_key_default_scopes(self):
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"

        api_key, _ = self.service.create_api_key(
            db=mock_db,
            user=mock_user,
            name="Test Key"
        )

        assert api_key.scopes == ["completions", "chat/completions"]

    def test_create_api_key_custom_scopes(self):
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"

        custom_scopes = ["completions"]
        api_key, _ = self.service.create_api_key(
            db=mock_db,
            user=mock_user,
            name="Test Key",
            scopes=custom_scopes
        )

        assert api_key.scopes == custom_scopes

    def test_validate_key_valid(self):
        key = self.service.generate_key()
        key_hash = self.service.hash_key(key)

        mock_db = MagicMock()
        mock_api_key = MagicMock()
        mock_api_key.key_hash = key_hash
        mock_api_key.is_active = True
        mock_api_key.expires_at = None

        mock_db.query.return_value.filter.return_value.first.return_value = mock_api_key

        result = self.service.validate_key(mock_db, key)
        assert result == mock_api_key

    def test_validate_key_invalid_prefix(self):
        mock_db = MagicMock()
        result = self.service.validate_key(mock_db, "invalid-key-format")
        assert result is None

    def test_validate_key_not_found(self):
        key = self.service.generate_key()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = self.service.validate_key(mock_db, key)
        assert result is None

    def test_validate_key_expired(self):
        key = self.service.generate_key()
        key_hash = self.service.hash_key(key)

        mock_db = MagicMock()
        mock_api_key = MagicMock()
        mock_api_key.key_hash = key_hash
        mock_api_key.is_active = True
        mock_api_key.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

        mock_db.query.return_value.filter.return_value.first.return_value = mock_api_key

        result = self.service.validate_key(mock_db, key)
        assert result is None

    def test_check_scope_full_access(self):
        mock_api_key = MagicMock()
        mock_api_key.scopes = ["*"]

        result = self.service.check_scope(mock_api_key, "any_scope")
        assert result is True

    def test_check_scope_matching(self):
        mock_api_key = MagicMock()
        mock_api_key.scopes = ["completions", "chat/completions"]

        result = self.service.check_scope(mock_api_key, "completions")
        assert result is True

    def test_check_scope_not_matching(self):
        mock_api_key = MagicMock()
        mock_api_key.scopes = ["completions"]

        result = self.service.check_scope(mock_api_key, "embeddings")
        assert result is False

    def test_get_user_keys(self):
        mock_db = MagicMock()
        user_id = "user-123"

        mock_keys = [
            MagicMock(id="key-1", name="Key 1"),
            MagicMock(id="key-2", name="Key 2")
        ]

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_keys

        result = self.service.get_user_keys(mock_db, user_id)
        assert len(result) == 2

    def test_revoke_key_success(self):
        mock_db = MagicMock()
        mock_api_key = MagicMock()
        mock_api_key.is_active = True

        mock_db.query.return_value.filter.return_value.first.return_value = mock_api_key

        result = self.service.revoke_key(mock_db, "key-123", "user-123")
        assert result is True
        assert mock_api_key.is_active is False
        mock_db.commit.assert_called_once()

    def test_revoke_key_not_found(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = self.service.revoke_key(mock_db, "nonexistent", "user-123")
        assert result is False
