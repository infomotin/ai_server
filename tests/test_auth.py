import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.services.auth import AuthService
from src.models.schemas import UserCreate


class TestAuthService:
    def setup_method(self):
        self.auth_service = AuthService()

    def test_hash_password(self):
        password = "test_password_123"
        hashed = self.auth_service.hash_password(password)

        assert hashed != password
        assert len(hashed) > 0
        assert hashed.startswith("$2b$")

    def test_verify_password_correct(self):
        password = "test_password_123"
        hashed = self.auth_service.hash_password(password)

        result = self.auth_service.verify_password(password, hashed)
        assert result is True

    def test_verify_password_incorrect(self):
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = self.auth_service.hash_password(password)

        result = self.auth_service.verify_password(wrong_password, hashed)
        assert result is False

    def test_create_access_token(self):
        user_id = "test-user-123"
        token = self.auth_service.create_access_token(user_id)

        assert token is not None
        assert len(token) > 0

    def test_decode_token_valid(self):
        user_id = "test-user-123"
        token = self.auth_service.create_access_token(user_id)

        payload = self.auth_service.decode_token(token)

        assert payload is not None
        assert payload["sub"] == user_id
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_token_invalid(self):
        payload = self.auth_service.decode_token("invalid-token")
        assert payload is None

    def test_decode_token_tampered(self):
        user_id = "test-user-123"
        token = self.auth_service.create_access_token(user_id)
        tampered_token = token[:-5] + "xxxxx"

        payload = self.auth_service.decode_token(tampered_token)
        assert payload is None

    def test_create_user(self):
        mock_db = MagicMock()
        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="password123"
        )

        user = self.auth_service.create_user(
            mock_db,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password
        )

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password_hash != "password123"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_authenticate_user_success(self):
        password = "test_password_123"
        hashed = self.auth_service.hash_password(password)

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.password_hash = hashed
        mock_user.is_active = True

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        result = self.auth_service.authenticate_user(mock_db, "test@example.com", password)
        assert result == mock_user

    def test_authenticate_user_wrong_password(self):
        hashed = self.auth_service.hash_password("correct_password")

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.password_hash = hashed
        mock_user.is_active = True

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        result = self.auth_service.authenticate_user(mock_db, "test@example.com", "wrong_password")
        assert result is None

    def test_authenticate_user_not_found(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = self.auth_service.authenticate_user(mock_db, "nonexistent@example.com", "password")
        assert result is None

    def test_authenticate_user_inactive(self):
        password = "test_password_123"
        hashed = self.auth_service.hash_password(password)

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.password_hash = hashed
        mock_user.is_active = False

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        result = self.auth_service.authenticate_user(mock_db, "test@example.com", password)
        assert result is None
