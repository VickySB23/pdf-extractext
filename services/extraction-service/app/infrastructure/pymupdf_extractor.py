from collections.abc import Callable

import pymupdf

from app.domain.extraction import (
    FORMATO_POR_DEFECTO,
    EncryptedPDFError,
    ExtractionResult,
    InvalidPDFError,
)
from app.infrastructure.markdown_converter import a_markdown

_MENSAJE_DANADO = "El PDF está dañado o no se pudo leer."


def _a_texto_plano(doc: pymupdf.Document) -> str:
    return "\n".join(page.get_text() for page in doc)


_EXTRACTORES: dict[str, Callable[[pymupdf.Document], str]] = {
    "markdown": a_markdown,
    "text": _a_texto_plano,
}


def extract_text(data: bytes, output_format: str = FORMATO_POR_DEFECTO) -> ExtractionResult:
    if not data.startswith(b"%PDF-"):
        raise InvalidPDFError("El contenido no parece un PDF (falta la firma %PDF-).")

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
