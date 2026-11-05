import httpx
import pytest

from app.application.interfaces.text_extractor import (
    EncryptedPDFError,
    ExtractorProtocolError,
    ExtractorUnavailableError,
    FileTooLargeError,
    InvalidPDFError,
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
    ex = make(
        lambda req: httpx.Response(200, json={"content": "hola", "page_count": 2})
    )
    r = await ex.extract("a.pdf", b"%PDF-")
    assert (r.text, r.pages) == ("hola", 2)


@pytest.mark.asyncio
async def test_texto_vacio_es_una_respuesta_valida():
    ex = make(lambda req: httpx.Response(200, json={"content": "", "page_count": 1}))
    r = await ex.extract("a.pdf", b"%PDF-")
    assert (r.text, r.pages) == ("", 1)


@pytest.mark.parametrize(
    ("status", "code", "error"),
    [
        (400, "invalid_pdf", InvalidPDFError),
        (400, "encrypted_pdf", EncryptedPDFError),
        (400, "no_text", NoTextError),
        (413, "too_large", FileTooLargeError),
    ],
)
@pytest.mark.asyncio
async def test_traduce_errores_de_entrada(status, code, error):
    ex = make(
        lambda req: httpx.Response(
            status, json={"detail": {"code": code, "message": "detalle"}}
        )
    )
    with pytest.raises(error):
        await ex.extract("a.pdf", b"%PDF-")


@pytest.mark.asyncio
async def test_4xx_desconocido_es_error_de_protocolo():
    ex = make(
        lambda req: httpx.Response(
            422, json={"detail": {"code": "desconocido", "message": "detalle"}}
        )
    )
    with pytest.raises(ExtractorProtocolError):
        await ex.extract("a.pdf", b"%PDF-")


@pytest.mark.asyncio
async def test_4xx_no_abre_el_circuito():
    breaker = CircuitBreaker(failure_threshold=1)
    ex = make(
        lambda req: httpx.Response(
            400, json={"detail": {"code": "invalid_pdf", "message": "dañado"}}
        ),
        breaker=breaker,
    )

    for _ in range(3):
        with pytest.raises(InvalidPDFError):
            await ex.extract("a.pdf", b"%PDF-")

    assert breaker.state == "closed"


@pytest.mark.asyncio
async def test_503_overloaded_propaga_retry_after():
    ex = make(
        lambda req: httpx.Response(
            503,
            json={"detail": {"code": "overloaded", "message": "saturado"}},
            headers={"Retry-After": "7"},
        )
    )
    with pytest.raises(ExtractorUnavailableError) as exc:
        await ex.extract("a.pdf", b"%PDF-")

    assert exc.value.retry_after == "7"


@pytest.mark.asyncio
async def test_500_es_indisponibilidad():
    ex = make(lambda req: httpx.Response(500, json={"detail": "boom"}))
    with pytest.raises(ExtractorUnavailableError) as exc:
        await ex.extract("a.pdf", b"%PDF-")

    assert exc.value.retry_after is None


@pytest.mark.asyncio
async def test_timeout_es_indisponibilidad():
    def handler(req):
        raise httpx.ReadTimeout("timeout", request=req)

    ex = make(handler)
    with pytest.raises(ExtractorUnavailableError):
        await ex.extract("a.pdf", b"%PDF-")


@pytest.mark.asyncio
async def test_error_de_conexion_es_indisponibilidad():
    ex = make(lambda req: (_ for _ in ()).throw(httpx.ConnectError("caído")))
    with pytest.raises(ExtractorUnavailableError):
        await ex.extract("a.pdf", b"%PDF-")


@pytest.mark.asyncio
async def test_5xx_abre_el_circuito_y_evita_la_llamada():
    breaker = CircuitBreaker(failure_threshold=2)
    llamadas = []

    def handler(req):
        llamadas.append(req)
        return httpx.Response(500, json={"detail": "boom"})

    ex = make(handler, breaker=breaker)

    for _ in range(2):
        with pytest.raises(ExtractorUnavailableError):
            await ex.extract("a.pdf", b"%PDF-")

    assert breaker.state == "open"
    with pytest.raises(ExtractorUnavailableError):
        await ex.extract("a.pdf", b"%PDF-")
    assert len(llamadas) == 2


@pytest.mark.asyncio
async def test_respuesta_no_json_es_error_de_protocolo():
    ex = make(lambda req: httpx.Response(200, text="no es json"))
    with pytest.raises(ExtractorProtocolError):
        await ex.extract("a.pdf", b"%PDF-")


@pytest.mark.asyncio
async def test_campos_faltantes_es_error_de_protocolo():
    ex = make(lambda req: httpx.Response(200, json={"content": "hola"}))
    with pytest.raises(ExtractorProtocolError):
        await ex.extract("a.pdf", b"%PDF-")


@pytest.mark.asyncio
async def test_page_count_invalido_es_error_de_protocolo():
    ex = make(
        lambda req: httpx.Response(200, json={"content": "hola", "page_count": "2"})
    )
    with pytest.raises(ExtractorProtocolError):
        await ex.extract("a.pdf", b"%PDF-")
