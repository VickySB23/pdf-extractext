"""Pruebas del ciclo de vida real de la aplicación."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI

from app import main


@pytest.mark.asyncio
async def test_lifespan_prepares_indexes_without_creating_folders(monkeypatch, tmp_path):
    repository = MagicMock()
    repository.ensure_indexes = AsyncMock()
    mongo_client = MagicMock()
    monkeypatch.setattr(
        main, "create_app_services", lambda: (MagicMock(), mongo_client, repository)
    )
    monkeypatch.chdir(tmp_path)

    async with main.lifespan(FastAPI()):
        repository.ensure_indexes.assert_awaited_once()

    mongo_client.close.assert_called_once()
    assert list(tmp_path.iterdir()) == []
