"""Lógica pura de extracción (sin FastAPI). Es el PDFService del monolito, aislado."""
import io
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError


class ExtractionError(Exception):
    code = "extraction_error"


class InvalidPDFError(ExtractionError):
    code = "invalid_pdf"


class EncryptedPDFError(ExtractionError):
    code = "encrypted_pdf"


@dataclass(frozen=True)
class ExtractionResult:
    content: str
    page_count: int


def extract_text(data: bytes) -> ExtractionResult:
    if not data.startswith(b"%PDF-"):
        raise InvalidPDFError("El contenido no parece un PDF (falta la firma %PDF-).")

    try:
        reader = PdfReader(io.BytesIO(data))
    except (PdfReadError, PdfStreamError, ValueError) as exc:
        raise InvalidPDFError("El PDF está dañado o no se pudo leer.") from exc

    if reader.is_encrypted:
        raise EncryptedPDFError("El PDF está protegido con contraseña.")

    try:
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except (PdfReadError, PdfStreamError, ValueError) as exc:
        raise InvalidPDFError("No se pudo extraer el texto del PDF.") from exc

    # Un PDF válido sin texto extraíble devuelve content vacío (no error)
    content = text.strip() if text else ""

    return ExtractionResult(content=content, page_count=len(reader.pages))
