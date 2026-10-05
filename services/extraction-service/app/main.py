import asyncio
import os

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from app.pdf_service import (
    EncryptedPDFError,
    ExtractionError,
    InvalidPDFError,
    extract_text,
)

MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", 10 * 1024 * 1024))

app = FastAPI(title="extraction-service", version="0.1.0")


class ExtractResponse(BaseModel):
    content: str
    page_count: int


# Cada error de dominio se traduce a un status HTTP y a un "code" estable
_STATUS = {
    InvalidPDFError: 400,
    EncryptedPDFError: 400,
}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/extract", response_model=ExtractResponse)
async def extract(request: Request):
    content_type = request.headers.get("content-type", "")

    if content_type.lower().startswith("multipart/form-data"):
        # Leer archivo desde multipart, campo "file"
        try:
            form = await request.form()
        except Exception:
            raise HTTPException(400, {"code": "invalid_pdf", "message": "Multipart inválido."})

        file = form.get("file")
        if file is None:
            # Intentar cualquier primer archivo
            for v in form.values():
                file = v
                break

        # Sin campo de archivo (form vacío o sólo campos de texto) -> 400, no 500
        if file is None or isinstance(file, str):
            raise HTTPException(
                400, {"code": "invalid_pdf", "message": "No se recibió ningún archivo."}
            )

        if hasattr(file, "file"):
            # UploadFile-like
            data = await file.read()
        else:
            # bytes directo
            data = file if isinstance(file, (bytes, bytearray)) else bytes(file)

        if not data:
            raise HTTPException(400, {"code": "invalid_pdf", "message": "Archivo vacío."})
        if len(data) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                413, {"code": "too_large", "message": "El archivo supera el tamaño máximo."}
            )
    else:
        # Body crudo: tratar como PDF. No usar request.body(), usar request.stream() con tope.
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                cl = int(content_length)
                if cl > MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        413, {"code": "too_large", "message": "El archivo supera el tamaño máximo."}
                    )
                if cl == 0:
                    raise HTTPException(
                        400, {"code": "invalid_pdf", "message": "Archivo vacío."}
                    )
            except ValueError:
                pass  # seguir leyendo por stream

        chunks: list[bytes] = []
        total = 0
        async for chunk in request.stream():
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_UPLOAD_SIZE_BYTES:
                raise HTTPException(
                    413, {"code": "too_large", "message": "El archivo supera el tamaño máximo."}
                )
        data = b"".join(chunks)

        if not data:
            raise HTTPException(400, {"code": "invalid_pdf", "message": "Archivo vacío."})
        # Validar firma %PDF- para crudo (incluso si content-type no es pdf)
        if not data.startswith(b"%PDF-"):
            raise HTTPException(
                400, {"code": "invalid_pdf", "message": "El contenido no parece un PDF (falta la firma %PDF-)."}
            )

    try:
        # pypdf es CPU-bound
        result = await asyncio.to_thread(extract_text, data)
    except ExtractionError as exc:
        raise HTTPException(
            _STATUS.get(type(exc), 400), {"code": exc.code, "message": str(exc)}
        )

    return ExtractResponse(content=result.content, page_count=result.page_count)
