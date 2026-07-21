from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200_when_mongo_ping_succeeds():
    mongo_client = MagicMock()
    mongo_client.admin.command = AsyncMock(return_value={"ok": 1})
    app.state.mongo_client = mongo_client

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    mongo_client.admin.command.assert_awaited_once_with("ping")


def test_health_returns_503_when_mongo_ping_fails():
    mongo_client = MagicMock()
    mongo_client.admin.command = AsyncMock(side_effect=Exception("mongo unavailable"))
    app.state.mongo_client = mongo_client

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy"}
    mongo_client.admin.command.assert_awaited_once_with("ping")
