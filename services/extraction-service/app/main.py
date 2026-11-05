import asyncio
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartParser

from app.consul_client import crear_registro
from app.logger import logger
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

# Invariante: debe ser menor que el timeout del cliente (Vegeta: 30 s).
QUEUE_TIMEOUT_SECONDS = _read_positive_int("QUEUE_TIMEOUT_SECONDS", 20)
RETRY_AFTER_SECONDS = _read_positive_int("RETRY_AFTER_SECONDS", 1)

# Margen para los límites y encabezados del multipart.
MULTIPART_OVERHEAD_BYTES = 1024 * 1024
# Starlette pasa a disco las partes de más de 1 MB; el PDF debe quedar en memoria.
MultiPartParser.spool_max_size = MAX_UPLOAD_SIZE_BYTES + MULTIPART_OVERHEAD_BYTES

OUTPUT_FORMAT = _read_choice("OUTPUT_FORMAT", FORMATO_POR_DEFECTO, FORMATOS)

# Sin esta variable el servicio corre solo, por ejemplo en desarrollo local.
CONSUL_URL = os.getenv("CONSUL_URL")

logger.info(
    "Configuración: QUEUE_TIMEOUT_SECONDS=%s MAX_UPLOAD_SIZE_BYTES=%s "
    "RETRY_AFTER_SECONDS=%s OUTPUT_FORMAT=%s",
    QUEUE_TIMEOUT_SECONDS,
    MAX_UPLOAD_SIZE_BYTES,
    RETRY_AFTER_SECONDS,
    OUTPUT_FORMAT,
)

# PyMuPDF no admite uso concurrente desde varios hilos: una extracción por réplica.
_CUPO = asyncio.Semaphore(1)


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    if CONSUL_URL is None:
        yield
        return
    async with httpx.AsyncClient(base_url=CONSUL_URL, timeout=5.0) as cliente:
        registro = crear_registro(cliente, CONSUL_URL)
        await registro.registrar()
        try:
            yield
        finally:
            await registro.desregistrar()


app = FastAPI(title="extraction-service", version="1.0.0", lifespan=ciclo_de_vida)


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


def _rechazar_si_content_length_excede(request: Request, es_multipart: bool) -> None:
    content_length = request.headers.get("content-length", "")
    if not content_length.isascii() or not content_length.isdigit():
        # El cuerpo crudo se corta al leerlo; el multipart se parsea completo.
        if es_multipart:
            raise _error(411, "length_required", "Falta el header Content-Length.")
        return
    declared = int(content_length)
    limite = MAX_UPLOAD_SIZE_BYTES + (MULTIPART_OVERHEAD_BYTES if es_multipart else 0)
    if declared > limite:
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
    try:
        await asyncio.wait_for(_CUPO.acquire(), timeout=QUEUE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning("Petición rechazada (overloaded): cola de %s s agotada.", QUEUE_TIMEOUT_SECONDS)
        raise _error(
            503,
            "overloaded",
            "El servicio está saturado. Reintentá en unos segundos.",
            {"Retry-After": str(RETRY_AFTER_SECONDS)},
        )
    try:
        yield
    finally:
        _CUPO.release()


@app.post("/extract", response_model=ExtractResponse)
async def extract(request: Request):
    es_multipart = request.headers.get("content-type", "").lower().startswith(
        "multipart/form-data"
    )
    _rechazar_si_content_length_excede(request, es_multipart)

    async with _lugar():
        # El cupo se adquiere antes de leer el cuerpo para no retener el PDF en memoria.
        data = await (_leer_multipart(request) if es_multipart else _leer_cuerpo_crudo(request))
        try:
            result = await asyncio.to_thread(extract_text, data, OUTPUT_FORMAT)
        except ExtractionError as exc:
            logger.warning("PDF rechazado (%s): %s", exc.code, exc)
            raise _error(400, exc.code, str(exc))
        return ExtractResponse(content=result.content, page_count=result.page_count)
