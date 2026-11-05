import httpx
import pytest

from app.application.interfaces.text_extractor import (
    EncryptedPDFError,
    ExtractorProtocolError,
    ExtractorUnavailableError,
    FileTooLargeError,
    InvalidPDFError,
)
from app.infrastructure.clients.http_text_extractor import HttpTextExtractor


async def no_wait(_seconds: float) -> None:
    return None


def make(handler):
    client = httpx.AsyncClient(
        base_url="http://extraction", transport=httpx.MockTransport(handler)
    )
    return HttpTextExtractor("http://extraction", client=client, wait=no_wait)


def counting(handler):
    calls = []

    def wrapper(request):
        calls.append(request)
        return handler(request)

    return wrapper, calls


@pytest.mark.asyncio
async def test_extract_ok():
    ex = make(
        lambda req: httpx.Response(200, json={"content": "hola", "page_count": 2})
    )
    r = await ex.extract(b"%PDF-")
    assert (r.text, r.pages) == ("hola", 2)


@pytest.mark.asyncio
async def test_envia_el_pdf_como_cuerpo_binario():
    recibidas = []

    def handler(req):
        recibidas.append(req)
        return httpx.Response(200, json={"content": "hola", "page_count": 1})

    await make(handler).extract(b"%PDF-1.7 datos")

    assert recibidas[0].content == b"%PDF-1.7 datos"
    assert recibidas[0].headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_texto_vacio_es_una_respuesta_valida():
    ex = make(lambda req: httpx.Response(200, json={"content": "", "page_count": 1}))
    r = await ex.extract(b"%PDF-")
    assert (r.text, r.pages) == ("", 1)


@pytest.mark.parametrize(
    ("status", "code", "error"),
    [
        (400, "invalid_pdf", InvalidPDFError),
        (400, "encrypted_pdf", EncryptedPDFError),
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
        await ex.extract(b"%PDF-")


@pytest.mark.asyncio
async def test_4xx_desconocido_es_error_de_protocolo():
    ex = make(
        lambda req: httpx.Response(
            422, json={"detail": {"code": "desconocido", "message": "detalle"}}
        )
    )
    with pytest.raises(ExtractorProtocolError):
        await ex.extract(b"%PDF-")


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
        await ex.extract(b"%PDF-")

    assert exc.value.retry_after == "7"


@pytest.mark.asyncio
async def test_500_es_indisponibilidad():
    ex = make(lambda req: httpx.Response(500, json={"detail": "boom"}))
    with pytest.raises(ExtractorUnavailableError) as exc:
        await ex.extract(b"%PDF-")

    assert exc.value.retry_after is None


@pytest.mark.asyncio
async def test_timeout_es_indisponibilidad():
    def handler(req):
        raise httpx.ReadTimeout("timeout", request=req)

    ex = make(handler)
    with pytest.raises(ExtractorUnavailableError):
        await ex.extract(b"%PDF-")


@pytest.mark.asyncio
async def test_error_de_conexion_es_indisponibilidad():
    ex = make(lambda req: (_ for _ in ()).throw(httpx.ConnectError("caído")))
    with pytest.raises(ExtractorUnavailableError):
        await ex.extract(b"%PDF-")


@pytest.mark.asyncio
async def test_respuesta_no_json_es_error_de_protocolo():
    ex = make(lambda req: httpx.Response(200, text="no es json"))
    with pytest.raises(ExtractorProtocolError):
        await ex.extract(b"%PDF-")


@pytest.mark.asyncio
async def test_campos_faltantes_es_error_de_protocolo():
    ex = make(lambda req: httpx.Response(200, json={"content": "hola"}))
    with pytest.raises(ExtractorProtocolError):
        await ex.extract(b"%PDF-")


@pytest.mark.asyncio
async def test_page_count_invalido_es_error_de_protocolo():
    ex = make(
        lambda req: httpx.Response(200, json={"content": "hola", "page_count": "2"})
    )
    with pytest.raises(ExtractorProtocolError):
        await ex.extract(b"%PDF-")


@pytest.mark.asyncio
async def test_reintenta_un_error_de_conexion():
    answers = iter([httpx.ConnectError("caído"), httpx.Response(200, json={"content": "hola", "page_count": 1})])

    def answer(_request):
        item = next(answers)
        if isinstance(item, Exception):
            raise item
        return item

    handler, calls = counting(answer)

    r = await make(handler).extract(b"%PDF-")

    assert r.text == "hola"
    assert len(calls) == 2


@pytest.mark.parametrize("status", [429, 502, 504])
@pytest.mark.asyncio
async def test_reintenta_fallos_rapidos_y_se_rinde(status):
    handler, calls = counting(
        lambda _request: httpx.Response(status, headers={"Retry-After": "2"})
    )

    with pytest.raises(ExtractorUnavailableError):
        await make(handler).extract(b"%PDF-")

    assert len(calls) == 3


@pytest.mark.asyncio
async def test_429_informa_saturacion_y_retry_after():
    handler, _ = counting(lambda _request: httpx.Response(429, headers={"Retry-After": "2"}))

    with pytest.raises(ExtractorUnavailableError) as exc:
        await make(handler).extract(b"%PDF-")

    assert exc.value.retry_after == "2"


@pytest.mark.asyncio
async def test_no_reintenta_un_503_de_cola_llena():
    handler, calls = counting(
        lambda _request: httpx.Response(503, json={"detail": {"code": "overloaded"}})
    )

    with pytest.raises(ExtractorUnavailableError):
        await make(handler).extract(b"%PDF-")

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_no_reintenta_un_timeout():
    def answer(request):
        raise httpx.ReadTimeout("timeout", request=request)

    handler, calls = counting(answer)

    with pytest.raises(ExtractorUnavailableError):
        await make(handler).extract(b"%PDF-")

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_no_reintenta_un_error_del_pdf():
    handler, calls = counting(
        lambda _request: httpx.Response(400, json={"detail": {"code": "invalid_pdf"}})
    )

    with pytest.raises(InvalidPDFError):
        await make(handler).extract(b"%PDF-")

    assert len(calls) == 1
