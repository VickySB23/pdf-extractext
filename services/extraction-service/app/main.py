import asyncio
import os
import weakref
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from starlette.datastructures import UploadFile

from app.pdf_service import (
    FORMATOS,
    FORMATO_POR_DEFECTO,
    ExtractionError,
    extract_text,
)


def _read_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        value = 0
    if value <= 0:
        raise RuntimeError(
            f"Variable de entorno inválida: {name}={raw!r} (se espera un entero positivo)."
        )
    return value


def _read_choice(name: str, default: str, opciones: tuple[str, ...]) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    valor = raw.strip().lower()
    if valor not in opciones:
        raise RuntimeError(
            f"Variable de entorno inválida: {name}={raw!r} "
            f"(se espera uno de: {', '.join(opciones)})."
        )
    return valor


MAX_UPLOAD_SIZE_BYTES = _read_positive_int("MAX_UPLOAD_SIZE_BYTES", 10 * 1024 * 1024)

MAX_CONCURRENT = _read_positive_int("MAX_CONCURRENT", 1)
# Invariante: debe ser menor que el timeout del cliente (Vegeta: 30 s).
QUEUE_TIMEOUT_SECONDS = _read_positive_int("QUEUE_TIMEOUT_SECONDS", 20)
RETRY_AFTER_SECONDS = _read_positive_int("RETRY_AFTER_SECONDS", 1)

OUTPUT_FORMAT = _read_choice("OUTPUT_FORMAT", FORMATO_POR_DEFECTO, FORMATOS)

# print y no logging: el dictConfig de uvicorn no configura el logger raíz.
print(
    "[extraction-service]"
    f" MAX_CONCURRENT={MAX_CONCURRENT}"
    f" QUEUE_TIMEOUT_SECONDS={QUEUE_TIMEOUT_SECONDS}"
    f" MAX_UPLOAD_SIZE_BYTES={MAX_UPLOAD_SIZE_BYTES}"
    f" RETRY_AFTER_SECONDS={RETRY_AFTER_SECONDS}"
    f" OUTPUT_FORMAT={OUTPUT_FORMAT}",
    flush=True,
)

# Un semáforo por event loop: TestClient/asyncio.run abren un loop por request.
_SEMAPHORES: (
    "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, tuple[int, asyncio.Semaphore]]"
) = weakref.WeakKeyDictionary()


def _get_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    cached = _SEMAPHORES.get(loop)
    if cached is not None and cached[0] == MAX_CONCURRENT:
        return cached[1]
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    _SEMAPHORES[loop] = (MAX_CONCURRENT, semaphore)
    return semaphore


app = FastAPI(title="extraction-service", version="0.1.0")


class ExtractResponse(BaseModel):
    content: str
    page_count: int


@app.get("/health")
async def health():
    return {"status": "healthy"}


def _error(
    status: int, code: str, message: str, headers: dict[str, str] | None = None
) -> HTTPException:
    return HTTPException(status, {"code": code, "message": message}, headers=headers)


def _rechazar_si_content_length_excede(request: Request) -> None:
    content_length = request.headers.get("content-length")
    if content_length is None:
        return
    try:
        declared = int(content_length)
    except ValueError:
        return
    if declared > MAX_UPLOAD_SIZE_BYTES:
        raise _error(413, "too_large", "El archivo supera el tamaño máximo.")
    if declared == 0:
        raise _error(400, "invalid_pdf", "Archivo vacío.")


async def _leer_multipart(request: Request) -> bytes:
    try:
        form = await request.form()
    except Exception:
        raise _error(400, "invalid_pdf", "Multipart inválido.")

    archivo = next((v for v in form.values() if isinstance(v, UploadFile)), None)
    if archivo is None:
        raise _error(400, "invalid_pdf", "No se recibió ningún archivo.")

    data = await archivo.read()
    if not data:
        raise _error(400, "invalid_pdf", "Archivo vacío.")
    if len(data) > MAX_UPLOAD_SIZE_BYTES:
        raise _error(413, "too_large", "El archivo supera el tamaño máximo.")
    return data


async def _leer_cuerpo_crudo(request: Request) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_UPLOAD_SIZE_BYTES:
            raise _error(413, "too_large", "El archivo supera el tamaño máximo.")
    data = b"".join(chunks)
    if not data:
        raise _error(400, "invalid_pdf", "Archivo vacío.")
    return data


@asynccontextmanager
async def _lugar():
    semaphore = _get_semaphore()
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=QUEUE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        raise _error(
            503,
            "overloaded",
            "El servicio está saturado. Reintentá en unos segundos.",
            {"Retry-After": str(RETRY_AFTER_SECONDS)},
        )
    try:
        yield
    finally:
        semaphore.release()


@app.post("/extract", response_model=ExtractResponse)
async def extract(request: Request):
    es_multipart = request.headers.get("content-type", "").lower().startswith(
        "multipart/form-data"
    )
    if not es_multipart:
        _rechazar_si_content_length_excede(request)

    async with _lugar():
        # El semáforo se adquiere antes de leer el cuerpo para no retener el PDF en memoria.
        data = await (_leer_multipart(request) if es_multipart else _leer_cuerpo_crudo(request))
        try:
            result = await asyncio.to_thread(extract_text, data, OUTPUT_FORMAT)
        except ExtractionError as exc:
            raise _error(400, exc.code, str(exc))
        return ExtractResponse(content=result.content, page_count=result.page_count)
