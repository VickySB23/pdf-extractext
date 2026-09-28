import httpx
import pytest

from app.application.interfaces.text_extractor import (
    ExtractorUnavailableError,
    NoTextError,
)
from app.infrastructure.clients.circuit_breaker import CircuitBreaker
from app.infrastructure.clients.http_text_extractor import HttpTextExtractor


def make(handler, **kw):
    client = httpx.AsyncClient(
        base_url="http://extraction", transport=httpx.MockTransport(handler)
    )
    return HttpTextExtractor("http://extraction", client=client, **kw)


@pytest.mark.asyncio
async def test_extract_ok():
    ex = make(lambda req: httpx.Response(200, json={"text": "hola", "checksum": "abc", "pages": 2}))
    r = await ex.extract("a.pdf", b"%PDF-")
    assert (r.text, r.checksum, r.pages) == ("hola", "abc", 2)


@pytest.mark.asyncio
async def test_traduce_error_de_dominio():
    ex = make(lambda req: httpx.Response(422, json={"detail": {"code": "no_text", "message": "sin texto"}}))
    with pytest.raises(NoTextError):
        await ex.extract("a.pdf", b"%PDF-")


@pytest.mark.asyncio
async def test_abre_el_circuito_si_el_servicio_cae():
    def boom(req):
        raise httpx.ConnectError("caído")

    ex = make(boom, breaker=CircuitBreaker(failure_threshold=2, reset_timeout=60))
    for _ in range(2):
        with pytest.raises(ExtractorUnavailableError):
            await ex.extract("a.pdf", b"%PDF-")
    assert ex._breaker.state == "open"
