"""Lógica pura de extracción (sin FastAPI)."""
import threading
from collections.abc import Callable
from dataclasses import dataclass

import pymupdf

from app.markdown_service import a_markdown

FORMATOS = ("markdown", "text")
FORMATO_POR_DEFECTO = "markdown"

_MENSAJE_DANADO = "El PDF está dañado o no se pudo leer."


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


def _a_texto_plano(doc: pymupdf.Document) -> str:
    return "\n".join(page.get_text() for page in doc)


_EXTRACTORES: dict[str, Callable[[pymupdf.Document], str]] = {
    "markdown": a_markdown,
    "text": _a_texto_plano,
}


def extract_text(data: bytes, output_format: str = FORMATO_POR_DEFECTO) -> ExtractionResult:
    """Extrae el texto de un PDF.

    output_format: "markdown" (default, Markdown básico) o "text" (plano,
    idéntico al comportamiento histórico). Cualquier otro valor es error de
    configuración y revienta con KeyError: main valida OUTPUT_FORMAT al
    arrancar, así que por HTTP es inalcanzable.
    """
    if not data.startswith(b"%PDF-"):
        raise InvalidPDFError("El contenido no parece un PDF (falta la firma %PDF-).")

    with _EXTRACTION_LOCK:
        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
        except (RuntimeError, ValueError) as exc:
            # pymupdf.FileDataError y pymupdf.EmptyFileError heredan de RuntimeError
            raise InvalidPDFError(_MENSAJE_DANADO) from exc

        with doc:
            # needs_pass: hay que descifrarlo. is_encrypted: cifrado de cualquier tipo.
            if doc.needs_pass or doc.is_encrypted:
                raise EncryptedPDFError("El PDF está protegido con contraseña.")

            page_count = doc.page_count
            # MuPDF repara los PDFs truncados en vez de fallar: quedan con 0 páginas.
            if page_count == 0:
                raise InvalidPDFError(_MENSAJE_DANADO)

            try:
                texto = _EXTRACTORES[output_format](doc)
            except (RuntimeError, ValueError) as exc:
                raise InvalidPDFError("No se pudo extraer el texto del PDF.") from exc

    # Un PDF válido sin texto extraíble devuelve content vacío (no error)
    return ExtractionResult(content=texto.strip(), page_count=page_count)
