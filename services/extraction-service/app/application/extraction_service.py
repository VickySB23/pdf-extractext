"""Caso de uso: extraer un PDF respetando el cupo de la réplica."""
import asyncio
from contextlib import asynccontextmanager

from app.core import config
from app.core.logger import logger
from app.domain.extraction import ExtractionResult, ServicioSaturadoError
from app.infrastructure.pymupdf_extractor import extract_text

# PyMuPDF no admite uso concurrente desde varios hilos: una extracción por réplica.
_CUPO = asyncio.Semaphore(1)


@asynccontextmanager
async def ocupar_cupo():
    try:
        await asyncio.wait_for(_CUPO.acquire(), timeout=config.QUEUE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        logger.warning(
            "Petición rechazada (overloaded): cola de %s s agotada.", config.QUEUE_TIMEOUT_SECONDS
        )
        raise ServicioSaturadoError() from exc
    try:
        yield
    finally:
        _CUPO.release()


async def extraer(data: bytes) -> ExtractionResult:
    return await asyncio.to_thread(extract_text, data, config.OUTPUT_FORMAT)
