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


# PyMuPDF no admite uso concurrente desde varios hilos; candado por proceso.
_EXTRACTION_LOCK = threading.Lock()


def _a_texto_plano(doc: pymupdf.Document) -> str:
    return "\n".join(page.get_text() for page in doc)


_EXTRACTORES: dict[str, Callable[[pymupdf.Document], str]] = {
    "markdown": a_markdown,
    "text": _a_texto_plano,
}


def extract_text(data: bytes, output_format: str = FORMATO_POR_DEFECTO) -> ExtractionResult:
    if not data.startswith(b"%PDF-"):
        raise InvalidPDFError("El contenido no parece un PDF (falta la firma %PDF-).")

    with _EXTRACTION_LOCK:
        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
        except (RuntimeError, ValueError) as exc:
            raise InvalidPDFError(_MENSAJE_DANADO) from exc

        with doc:
            if doc.needs_pass or doc.is_encrypted:
                raise EncryptedPDFError("El PDF está protegido con contraseña.")

            page_count = doc.page_count
            # MuPDF repara PDFs truncados en vez de fallar; 0 páginas es error.
            if page_count == 0:
                raise InvalidPDFError(_MENSAJE_DANADO)

            try:
                texto = _EXTRACTORES[output_format](doc)
            except (RuntimeError, ValueError) as exc:
                raise InvalidPDFError("No se pudo extraer el texto del PDF.") from exc

    return ExtractionResult(content=texto.strip(), page_count=page_count)
