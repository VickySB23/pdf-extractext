"""Puerto (interfaz) que DocumentService usa para extraer texto.

DocumentService depende de esta abstracción, no de pypdf ni de HTTP:
así la extracción puede vivir en otro microservicio sin tocar la lógica de negocio.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ExtractedText:
    text: str
    checksum: str
    pages: int


class TextExtractionError(Exception):
    """Base de los errores de extracción."""


class InvalidPDFError(TextExtractionError):
    pass


class EncryptedPDFError(TextExtractionError):
    pass


class NoTextError(TextExtractionError):
    pass


class ExtractorUnavailableError(TextExtractionError):
    """El extraction-service no responde o el circuito está abierto."""


class TextExtractor(Protocol):
    async def extract(self, filename: str, content: bytes) -> ExtractedText: ...
