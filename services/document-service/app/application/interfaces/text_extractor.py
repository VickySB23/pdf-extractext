"""Puerto (interfaz) que DocumentService usa para extraer texto.

DocumentService depende de esta abstracción, no de HTTP:
así la extracción puede vivir en otro microservicio sin tocar la lógica de negocio.
El checksum se calcula en la capa de aplicación sobre los bytes del archivo.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ExtractedText:
    text: str
    pages: int


class TextExtractionError(Exception):
    """Base de los errores de extracción."""


class InvalidPDFError(TextExtractionError):
    pass


class EncryptedPDFError(TextExtractionError):
    pass


class NoTextError(TextExtractionError):
    pass


class FileTooLargeError(TextExtractionError):
    pass


class ExtractorUnavailableError(TextExtractionError):
    """El extraction-service no responde o el circuito está abierto."""

    def __init__(self, message: str, retry_after: str | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ExtractorProtocolError(TextExtractionError):
    """El extraction-service devolvió una respuesta que no respeta el contrato."""


class TextExtractor(Protocol):
    async def extract(self, filename: str, content: bytes) -> ExtractedText: ...
