import asyncio
import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.pdf_service import (
    EncryptedPDFError,
    ExtractionError,
    InvalidPDFError,
    NoTextError,
    extract_text,
)

MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", 10 * 1024 * 1024))

app = FastAPI(title="extraction-service", version="0.1.0")


class ExtractResponse(BaseModel):
    text: str
    checksum: str
    pages: int


# Cada error de dominio se traduce a un status HTTP y a un "code" estable
# que el document-service usa para reconstruir la excepción del otro lado.
_STATUS = {
    InvalidPDFError: 400,
    EncryptedPDFError: 400,
    NoTextError: 422,
}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/extract", response_model=ExtractResponse)
async def extract(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(400, {"code": "invalid_pdf", "message": "Archivo vacío."})
    if len(data) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            413, {"code": "too_large", "message": "El archivo supera el tamaño máximo."}
        )
    try:
        # pypdf es CPU-bound: lo sacamos del event loop
        result = await asyncio.to_thread(extract_text, data)
    except ExtractionError as exc:
        raise HTTPException(
            _STATUS.get(type(exc), 400), {"code": exc.code, "message": str(exc)}
        )
    return ExtractResponse(text=result.text, checksum=result.checksum, pages=result.pages)
