import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.services.model_service import ModelService, DEFAULT_MODELS
from src.models.database import Model


class TestModelService:
    def setup_method(self):
        self.service = ModelService()

    def test_default_models_exist(self):
        assert len(DEFAULT_MODELS) > 0
        assert any(m["id"] == "llama3.2:1b" for m in DEFAULT_MODELS)

    def test_default_model_in_config(self):
        assert self.service.default_model == "llama3.2:1b"

    def test_get_all_models_empty_db(self):
        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = []

        models = self.service.get_all_models(mock_db)
        assert models == []

    def test_get_downloaded_models(self):
        mock_db = MagicMock()
        mock_models = [
            MagicMock(id="model-1", is_downloaded=True),
            MagicMock(id="model-2", is_downloaded=False)
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_models[:1]

        models = self.service.get_downloaded_models(mock_db)
        assert len(models) == 1

    def test_get_model(self):
        mock_db = MagicMock()
        mock_model = MagicMock(id="llama3.2:1b")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_model

        result = self.service.get_model(mock_db, "llama3.2:1b")
        assert result == mock_model

    def test_get_model_not_found(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = self.service.get_model(mock_db, "nonexistent")
        assert result is None

    def test_estimate_model_size_known(self):
        size = self.service.estimate_model_size("llama3.2:1b")
        assert size is not None
        assert size > 0

    def test_estimate_model_size_unknown(self):
        size = self.service.estimate_model_size("unknown-model")
        assert size is None

    def test_init_default_models(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        self.service.init_default_models(mock_db)

        assert mock_db.add.call_count == len(DEFAULT_MODELS)
        mock_db.commit.assert_called_once()


class TestModelDefaults:
    def test_default_model_has_required_fields(self):
        for model in DEFAULT_MODELS:
            assert "id" in model
            assert "name" in model
            assert "provider" in model
            assert model["provider"] == "ollama"

    def test_models_under_2gb_parameter_count(self):
        for model in DEFAULT_MODELS:
            if "qwen" in model["id"] or "llama3.2" in model["id"]:
                params = model.get("parameter_count", 0)
                assert params <= 2_000_000_000, f"{model['id']} exceeds 2B parameters"

    def test_model_ids_are_unique(self):
        ids = [m["id"] for m in DEFAULT_MODELS]
        assert len(ids) == len(set(ids))
