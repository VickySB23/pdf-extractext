"""Lógica pura de extracción (sin FastAPI). Es el PDFService del monolito, aislado."""
import threading
from dataclasses import dataclass

import pymupdf


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


# PyMuPDF no se puede usar desde varios hilos a la vez ("PyMuPDF does not support
# running on multiple threads"), así que dentro del proceso las extracciones se
# serializan. El paralelismo real se consigue con réplicas (procesos/contenedores),
# no con hilos.
_EXTRACTION_LOCK = threading.Lock()


def extract_text(data: bytes) -> ExtractionResult:
    if not data.startswith(b"%PDF-"):
        raise InvalidPDFError("El contenido no parece un PDF (falta la firma %PDF-).")

    with _EXTRACTION_LOCK:
        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
        except (RuntimeError, ValueError) as exc:
            # pymupdf.FileDataError y pymupdf.EmptyFileError heredan de RuntimeError
            raise InvalidPDFError("El PDF está dañado o no se pudo leer.") from exc

        try:
            # needs_pass: hay que descifrarlo. is_encrypted: cifrado de cualquier tipo.
            if doc.needs_pass or doc.is_encrypted:
                raise EncryptedPDFError("El PDF está protegido con contraseña.")

            page_count = doc.page_count
            # MuPDF repara los PDFs truncados en vez de fallar: quedan con 0 páginas.
            if page_count == 0:
                raise InvalidPDFError("El PDF está dañado o no se pudo leer.")

            try:
                text = "\n".join(page.get_text() for page in doc)
            except (RuntimeError, ValueError) as exc:
                raise InvalidPDFError("No se pudo extraer el texto del PDF.") from exc
        finally:
            # Siempre cerrar: sin esto el documento nativo y su memoria se pierden.
            doc.close()

        # Un PDF válido sin texto extraíble devuelve content vacío (no error)
        content = text.strip() if text else ""

    return ExtractionResult(content=content, page_count=page_count)