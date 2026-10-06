"""Lógica pura de extracción (sin FastAPI). Es el PDFService del monolito, aislado."""
import threading
from dataclasses import dataclass

import pymupdf

from app.markdown_service import a_markdown


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


def extract_text(data: bytes, output_format: str = "markdown") -> ExtractionResult:
    """Extrae el texto de un PDF.

    output_format: "markdown" (default, Markdown básico) o "text" (plano,
    idéntico al comportamiento histórico). Un valor desconocido lanza
    ValueError: es un error de configuración, no un PDF inválido (main valida
    OUTPUT_FORMAT al arrancar, así que por HTTP es inalcanzable).
    """
    if not data.startswith(b"%PDF-"):
        raise InvalidPDFError("El contenido no parece un PDF (falta la firma %PDF-).")
    # Validación estricta ANTES del lock y fuera del try que traduce
    # (RuntimeError, ValueError) -> InvalidPDFError.
    if output_format not in ("markdown", "text"):
        raise ValueError(f"Formato de salida desconocido: {output_format!r}")

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
                if output_format == "text":
                    text = "\n".join(page.get_text() for page in doc)
                else:
                    text = a_markdown(doc)
            except (RuntimeError, ValueError) as exc:
                raise InvalidPDFError("No se pudo extraer el texto del PDF.") from exc
        finally:
            # Siempre cerrar: sin esto el documento nativo y su memoria se pierden.
            doc.close()

        # Un PDF válido sin texto extraíble devuelve content vacío (no error)
        content = text.strip() if text else ""

    return ExtractionResult(content=content, page_count=page_count)