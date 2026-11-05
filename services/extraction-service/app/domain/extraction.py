"""Conceptos del dominio: formatos, resultado y errores de la extracción."""
from dataclasses import dataclass

FORMATOS = ("markdown", "text")
FORMATO_POR_DEFECTO = "markdown"


class ExtractionError(Exception):
    code: str


class InvalidPDFError(ExtractionError):
    code = "invalid_pdf"


class EncryptedPDFError(ExtractionError):
    code = "encrypted_pdf"


class ServicioSaturadoError(Exception):
    """La petición agotó su tiempo de espera en la cola."""


@dataclass(frozen=True)
class ExtractionResult:
    content: str
    page_count: int
