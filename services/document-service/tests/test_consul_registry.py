import json
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from app import main
from app.core import get_settings
from app.infrastructure.clients.consul_registry import ConsulRegistry
from app.infrastructure.repositories.mongo_repository import MongoDocumentRepository


async def no_wait(_seconds: float) -> None:
    return None


def registry(handler, **kw) -> ConsulRegistry:
    client = httpx.AsyncClient(
        base_url="http://consul:8500", transport=httpx.MockTransport(handler)
    )
    return ConsulRegistry(
        "http://consul:8500", client=client, ip="172.20.0.6", instance_id="document-service-abc", **kw
    )


@pytest.mark.asyncio
async def test_registers_with_own_id_and_http_check():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200)

    await registry(handler).register()

    assert requests[0].method == "PUT"
    assert requests[0].url.path == "/v1/agent/service/register"
    body = json.loads(requests[0].content)
    assert body["ID"] == "document-service-abc"
    assert body["Port"] == 8000
    assert body["Check"]["HTTP"] == "http://172.20.0.6:8000/health"
    assert "traefik.enable=true" in body["Tags"]


@pytest.mark.asyncio
async def test_retries_until_consul_answers():
    answers = iter([httpx.ConnectError("caído"), httpx.Response(500), httpx.Response(200)])

    def handler(_request):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    await registry(handler, wait=no_wait).register()

    assert next(answers, None) is None


@pytest.mark.asyncio
async def test_fails_when_consul_never_answers():
    with pytest.raises(RuntimeError, match="Consul"):
        await registry(lambda _request: httpx.Response(500), wait=no_wait).register()


@pytest.mark.asyncio
async def test_deregisters_with_its_id_and_closes_the_client():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200)

    consul = registry(handler)
    await consul.deregister()

    assert requests[0].url.path == "/v1/agent/service/deregister/document-service-abc"
    assert consul._client.is_closed


@pytest.mark.asyncio
async def test_deregister_does_not_break_shutdown():
    def handler(_request):
        raise httpx.ConnectError("caído")

    await registry(handler).deregister()


@pytest.mark.asyncio
async def test_lifespan_registers_and_deregisters(monkeypatch):
    monkeypatch.setenv("CONSUL_URL", "http://consul:8500")
    get_settings.cache_clear()
    monkeypatch.setattr(MongoDocumentRepository, "ensure_indexes", AsyncMock())
    consul = AsyncMock()
    monkeypatch.setattr(main, "ConsulRegistry", lambda _url: consul)

    async with main.lifespan(FastAPI()):
        consul.register.assert_awaited_once()
        consul.deregister.assert_not_awaited()

    consul.deregister.assert_awaited_once()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_lifespan_skips_consul_without_url(monkeypatch):
    monkeypatch.delenv("CONSUL_URL", raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr(MongoDocumentRepository, "ensure_indexes", AsyncMock())
    monkeypatch.setattr(main, "ConsulRegistry", lambda _url: pytest.fail("no debe registrarse"))

    async with main.lifespan(FastAPI()):
        pass

    get_settings.cache_clear()
