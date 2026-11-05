"""Configuración leída del entorno y validada al arrancar."""
import os

from app.core.logger import logger
from app.domain.extraction import FORMATO_POR_DEFECTO, FORMATOS


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
# Margen para los límites y encabezados del multipart.
MULTIPART_OVERHEAD_BYTES = 1024 * 1024

# Invariante: debe ser menor que el timeout del cliente (Vegeta: 30 s).
QUEUE_TIMEOUT_SECONDS = _read_positive_int("QUEUE_TIMEOUT_SECONDS", 20)
RETRY_AFTER_SECONDS = _read_positive_int("RETRY_AFTER_SECONDS", 1)

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
