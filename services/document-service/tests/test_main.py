"""Pruebas del ensamblado real de la aplicación, sin reemplazar dependencias."""
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI

from app.application.services.document_service import DocumentService
from app.core import get_settings
from app.infrastructure.clients.http_text_extractor import HttpTextExtractor
from app.infrastructure.repositories.mongo_repository import MongoDocumentRepository
from app.main import create_app_services, lifespan


@pytest.fixture
def extraction_env(monkeypatch):
    monkeypatch.setenv("EXTRACTION_URL", "http://extraction-test:8001")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_create_app_services_wires_extractor_from_settings(extraction_env):
    document_service, mongo_client, extractor, _ = create_app_services()
    try:
        assert isinstance(document_service, DocumentService)
        assert isinstance(extractor, HttpTextExtractor)
        assert str(extractor._client.base_url) == "http://extraction-test:8001"
    finally:
        await mongo_client.close()
        await extractor.aclose()


@pytest.mark.asyncio
async def test_lifespan_prepares_indexes_and_closes_the_extractor(extraction_env, monkeypatch):
    ensure_indexes = AsyncMock()
    monkeypatch.setattr(MongoDocumentRepository, "ensure_indexes", ensure_indexes)
    app = FastAPI()

    async with lifespan(app):
        ensure_indexes.assert_awaited_once()
        client = app.state.text_extractor._client
        assert not client.is_closed

    assert client.is_closed
