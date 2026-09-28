"""Lógica pura de extracción (sin FastAPI). Es el PDFService del monolito, aislado."""
import hashlib
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


class NoTextError(ExtractionError):
    code = "no_text"


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    checksum: str
    pages: int


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
        text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except (PdfReadError, PdfStreamError, ValueError) as exc:
        raise InvalidPDFError("No se pudo extraer el texto del PDF.") from exc

    if not text:
        raise NoTextError("El PDF no tiene texto nativo extraíble (¿es un escaneo?).")

    checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return ExtractionResult(text=text, checksum=checksum, pages=len(reader.pages))
