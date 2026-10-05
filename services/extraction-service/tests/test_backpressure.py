"""Backpressure de POST /extract: semáforo, espera acotada y liberación siempre.

Sin pytest-asyncio: cada test corre un asyncio.run con httpx.AsyncClient +
ASGITransport. ASGITransport ejecuta la app en el loop del test, así que todas
las requests de un test compiten por el MISMO semáforo (que es lo que queremos).
"""
import asyncio
import threading
import time

import httpx

from app import main
from app.pdf_service import ExtractionResult
from app.pdf_service import extract_text as _extract_real
from tests.conftest import build_pdf

PDF_HEADERS = {"Content-Type": "application/pdf"}
TIMEOUT_HTTPX = 30.0  # las requests de los tests no deben expirar


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app),
        base_url="http://testserver",
        timeout=TIMEOUT_HTTPX,
    )


class ExtractorFalso:
    """Reemplaza app.main.extract_text (el handler lo corre con asyncio.to_thread).

    Registra el texto de cada PDF en `orden` (para verificar el FIFO) y, con
    bloquear=True, queda esperando un signal para mantener tomado el slot del
    semáforo desde el test. El wait tiene tope: si el test falla antes de
    liberar, la suite no se cuelga.
    """

    def __init__(self, demora: float = 0.05, *, bloquear: bool = False, orden=None):
        self.demora = demora
        self.bloquear = bloquear
        self.orden = [] if orden is None else orden
        self.entró = threading.Event()
        self.salir = threading.Event()

    def __call__(self, data: bytes) -> ExtractionResult:
        real = _extract_real(data)  # el _EXTRACTION_LOCK se libera acá
        self.orden.append(real.content)
        self.entró.set()
        if self.bloquear:
            assert self.salir.wait(timeout=10), "el test no liberó la extracción"
            return real
        time.sleep(self.demora)
        return real


def test_503_con_retry_after_si_la_espera_supera_el_tope(monkeypatch):
    """(a) MAX_CONCURRENT=1 y espera corta: la segunda petición se rechaza."""
    monkeypatch.setattr(main, "MAX_CONCURRENT", 1)
    monkeypatch.setattr(main, "QUEUE_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(main, "RETRY_AFTER_SECONDS", 3)
    extractor = ExtractorFalso(bloquear=True)
    monkeypatch.setattr(main, "extract_text", extractor)

    async def scenario():
        async with _client() as cliente:
            primera = asyncio.create_task(
                cliente.post("/extract", content=build_pdf("primera"), headers=PDF_HEADERS)
            )
            # la primera tiene que tener el slot antes de que llegue la segunda
            assert await asyncio.to_thread(extractor.entró.wait, 5) is True
            t0 = time.perf_counter()
            segunda = await cliente.post(
                "/extract", content=build_pdf("segunda"), headers=PDF_HEADERS
            )
            espera = time.perf_counter() - t0
            extractor.salir.set()
            r1 = await primera
            return r1, segunda, espera, main._get_semaphore()._value

    r1, r2, espera, permisos = asyncio.run(scenario())

    assert r1.status_code == 200 and r1.json()["content"] == "primera"
    assert r2.status_code == 503
    assert r2.json()["detail"]["code"] == "overloaded"
    assert r2.headers["retry-after"] == "3"
    assert 0.15 <= espera < 3.0  # cortó por el timeout, no esperó a que se liberara
    assert permisos == 1  # ningún permiso quedó perdido


def test_413_por_content_length_no_consume_el_semáforo(monkeypatch):
    """El rechazo barato va antes del semáforo: no hace cola ni gasta CPU."""
    monkeypatch.setattr(main, "MAX_CONCURRENT", 1)
    monkeypatch.setattr(main, "QUEUE_TIMEOUT_SECONDS", 0.2)
    # El límite calza justo con el PDF que va a ocupar el slot: el que se
    # rechaza tiene Content-Length mayor y ni siquiera llega a leerse.
    pdf_ocupa = build_pdf("ocupa")
    monkeypatch.setattr(main, "MAX_UPLOAD_SIZE_BYTES", len(pdf_ocupa))
    extractor = ExtractorFalso(bloquear=True)
    monkeypatch.setattr(main, "extract_text", extractor)

    async def scenario():
        async with _client() as cliente:
            ocupa = asyncio.create_task(
                cliente.post("/extract", content=pdf_ocupa, headers=PDF_HEADERS)
            )
            assert await asyncio.to_thread(extractor.entró.wait, 5) is True
            t0 = time.perf_counter()
            r413 = await cliente.post(
                "/extract", content=b"x" * (len(pdf_ocupa) + 1), headers=PDF_HEADERS
            )
            dt = time.perf_counter() - t0
            extractor.salir.set()
            await ocupa
            return r413, dt

    r413, dt = asyncio.run(scenario())

    assert r413.status_code == 413
    assert r413.json()["detail"]["code"] == "too_large"
    assert dt < 0.15  # no esperó el semáforo (el tope de cola es 0.2 s)


def test_las_peticiones_simultaneas_se_atienden_en_fila(monkeypatch):
    """(b) si hay lugar, todas se atienden y en orden de llegada."""
    monkeypatch.setattr(main, "MAX_CONCURRENT", 1)
    monkeypatch.setattr(main, "QUEUE_TIMEOUT_SECONDS", 20)
    orden: list[str] = []
    extractor = ExtractorFalso(demora=0.05, orden=orden)
    monkeypatch.setattr(main, "extract_text", extractor)

    async def scenario():
        async with _client() as cliente:
            tasks = []
            for i in range(4):
                if i:
                    await asyncio.sleep(0.01)  # escalonar: así se acumulan en la cola
                tasks.append(
                    asyncio.create_task(
                        cliente.post(
                            "/extract", content=build_pdf(f"pdf-{i}"), headers=PDF_HEADERS
                        )
                    )
                )
            return await asyncio.gather(*tasks)

    respuestas = asyncio.run(scenario())

    assert [r.status_code for r in respuestas] == [200, 200, 200, 200]
    assert [r.json()["content"] for r in respuestas] == ["pdf-0", "pdf-1", "pdf-2", "pdf-3"]
    assert orden == ["pdf-0", "pdf-1", "pdf-2", "pdf-3"]  # FIFO del semáforo


def test_el_semáforo_queda_libre_tras_un_error(monkeypatch):
    """(c) después de un error de extracción el semáforo queda libre."""
    monkeypatch.setattr(main, "MAX_CONCURRENT", 1)
    monkeypatch.setattr(main, "QUEUE_TIMEOUT_SECONDS", 5)
    # extract_text REAL y un PDF truncado: el InvalidPDFError pasa adentro de la
    # extracción (con el slot tomado), no con un 400 previo por la firma %PDF-.
    pdf = build_pdf("hola")
    truncado = pdf[: len(pdf) // 10]

    async def scenario():
        async with _client() as cliente:
            r_error = await cliente.post("/extract", content=truncado, headers=PDF_HEADERS)
            r_ok = await cliente.post(
                "/extract", content=build_pdf("despues del error"), headers=PDF_HEADERS
            )
            return r_error, r_ok, main._get_semaphore()._value

    r_error, r_ok, permisos = asyncio.run(scenario())

    assert r_error.status_code == 400 and r_error.json()["detail"]["code"] == "invalid_pdf"
    assert r_ok.status_code == 200 and r_ok.json()["content"] == "despues del error"
    assert permisos == 1


def test_health_responde_200_mientras_hay_extraccion_en_curso(monkeypatch):
    """(d) /health no pasa por el semáforo: responde aunque esté saturado."""
    monkeypatch.setattr(main, "MAX_CONCURRENT", 1)
    monkeypatch.setattr(main, "QUEUE_TIMEOUT_SECONDS", 10)
    extractor = ExtractorFalso(bloquear=True)
    monkeypatch.setattr(main, "extract_text", extractor)

    async def scenario():
        async with _client() as cliente:
            en_curso = asyncio.create_task(
                cliente.post("/extract", content=build_pdf("lenta"), headers=PDF_HEADERS)
            )
            assert await asyncio.to_thread(extractor.entró.wait, 5) is True
            health = await cliente.get("/health")
            extractor.salir.set()
            return health, await en_curso

    health, r = asyncio.run(scenario())

    assert health.status_code == 200
    assert health.json() == {"status": "healthy"}
    assert r.status_code == 200