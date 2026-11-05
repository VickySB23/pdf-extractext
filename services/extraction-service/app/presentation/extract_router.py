"""Capa HTTP: lee el cuerpo, valida sus límites y traduce los errores."""
from fastapi import APIRouter, HTTPException, Request
from starlette.datastructures import UploadFile

from app.application.extraction_service import extraer, ocupar_cupo
from app.core import config
from app.core.logger import logger
from app.domain.extraction import ExtractionError, ServicioSaturadoError
from app.presentation.schemas import ExtractResponse

router = APIRouter(tags=["extraction"])


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
    limite = config.MAX_UPLOAD_SIZE_BYTES + (config.MULTIPART_OVERHEAD_BYTES if es_multipart else 0)
    if declared > limite:
        raise _error(413, "too_large", "El archivo supera el tamaño máximo.")
    if declared == 0:
        raise _error(400, "invalid_pdf", "Archivo vacío.")


async def _leer_multipart(request: Request) -> bytes:
    try:
        form = await request.form()
    except Exception as exc:
        raise _error(400, "invalid_pdf", "Multipart inválido.") from exc

    archivo = next((v for v in form.values() if isinstance(v, UploadFile)), None)
    if archivo is None:
        raise _error(400, "invalid_pdf", "No se recibió ningún archivo.")

    data = await archivo.read()
    if not data:
        raise _error(400, "invalid_pdf", "Archivo vacío.")
    if len(data) > config.MAX_UPLOAD_SIZE_BYTES:
        raise _error(413, "too_large", "El archivo supera el tamaño máximo.")
    return data


async def _leer_cuerpo_crudo(request: Request) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        chunks.append(chunk)
        total += len(chunk)
        if total > config.MAX_UPLOAD_SIZE_BYTES:
            raise _error(413, "too_large", "El archivo supera el tamaño máximo.")
    data = b"".join(chunks)
    if not data:
        raise _error(400, "invalid_pdf", "Archivo vacío.")
    return data


@router.post("/extract", response_model=ExtractResponse)
async def extract(request: Request):
    es_multipart = request.headers.get("content-type", "").lower().startswith(
        "multipart/form-data"
    )
    _rechazar_si_content_length_excede(request, es_multipart)

    try:
        async with ocupar_cupo():
            # El cupo se adquiere antes de leer el cuerpo para no retener el PDF en memoria.
            data = await (_leer_multipart(request) if es_multipart else _leer_cuerpo_crudo(request))
            result = await extraer(data)
    except ServicioSaturadoError as exc:
        raise _error(
            503,
            "overloaded",
            "El servicio está saturado. Reintentá en unos segundos.",
            {"Retry-After": str(config.RETRY_AFTER_SECONDS)},
        ) from exc
    except ExtractionError as exc:
        logger.warning("PDF rechazado (%s): %s", exc.code, exc)
        raise _error(400, exc.code, str(exc)) from exc
    return ExtractResponse(content=result.content, page_count=result.page_count)
