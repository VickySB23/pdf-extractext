import asyncio
import os
import weakref

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from app.pdf_service import (
    EncryptedPDFError,
    ExtractionError,
    InvalidPDFError,
    extract_text,
)


def _read_positive_int(name: str, default: int) -> int:
    """Lee una variable de entorno como entero positivo (> 0).

    Sin definir -> default. Definida pero inválida -> RuntimeError al arrancar
    (importar este módulo ES arrancar el servicio), con el nombre en el mensaje.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        value = 0
    if value <= 0:
        raise RuntimeError(
            f"Variable de entorno inválida: {name}={raw!r} (se espera un entero positivo)."
        )
    return value


def _read_choice(name: str, default: str, opciones: tuple[str, ...]) -> str:
    """Lee una variable de entorno acotada a un conjunto de valores.

    Sin definir -> default. Definida pero inválida -> RuntimeError al arrancar
    (importar este módulo ES arrancar el servicio), con el nombre y las opciones
    esperadas en el mensaje. Se compara en minúsculas y sin espacios borde.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    valor = raw.strip().lower()
    if valor not in opciones:
        raise RuntimeError(
            f"Variable de entorno inválida: {name}={raw!r} "
            f"(se espera uno de: {', '.join(opciones)})."
        )
    return valor


MAX_UPLOAD_SIZE_BYTES = _read_positive_int("MAX_UPLOAD_SIZE_BYTES", 10 * 1024 * 1024)

# Backpressure: cuántos PDF pueden estar "en vuelo" (descargados + extrayéndose)
# al mismo tiempo. Los que esperan, esperan SIN tener el PDF en memoria.
MAX_CONCURRENT = _read_positive_int("MAX_CONCURRENT", 1)
# Tope de espera por un lugar en el semáforo. Si se agota: 503 + Retry-After.
#
# Invariante: debe ser MENOR que el timeout del cliente (Vegeta usa 30 s).
# Así toda petición que se procesa aún tiene un cliente esperando y no se
# gasta CPU en peticiones abandonadas.
QUEUE_TIMEOUT_SECONDS = _read_positive_int("QUEUE_TIMEOUT_SECONDS", 20)
RETRY_AFTER_SECONDS = _read_positive_int("RETRY_AFTER_SECONDS", 1)

# Formato de "content": Markdown básico (default) o texto plano.
OUTPUT_FORMAT = _read_choice("OUTPUT_FORMAT", "markdown", ("markdown", "text"))

# Twelve-Factor: se anuncia la configuración efectiva por stdout al arrancar.
# NO usar logging.getLogger(...).info() acá: el dictConfig de uvicorn no
# configura el logger root, así que un INFO de un logger nuevo se pierde.
print(
    "[extraction-service]"
    f" MAX_CONCURRENT={MAX_CONCURRENT}"
    f" QUEUE_TIMEOUT_SECONDS={QUEUE_TIMEOUT_SECONDS}"
    f" MAX_UPLOAD_SIZE_BYTES={MAX_UPLOAD_SIZE_BYTES}"
    f" RETRY_AFTER_SECONDS={RETRY_AFTER_SECONDS}"
    f" OUTPUT_FORMAT={OUTPUT_FORMAT}",
    flush=True,
)

# Un semáforo por event loop. En producción hay uno solo (el Dockerfile no usa
# --workers), pero los tests abren un loop nuevo por request (TestClient) o por
# asyncio.run, y un asyncio.Semaphore queda atado al loop en el que esperó
# (_LoopBoundMixin._get_loop). WeakKeyDictionary para no retener loops muertos.
_SEMAPHORES: (
    "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, tuple[int, asyncio.Semaphore]]"
) = weakref.WeakKeyDictionary()


def _get_semaphore() -> asyncio.Semaphore:
    """Semáforo con MAX_CONCURRENT permisos para el loop actual."""
    loop = asyncio.get_running_loop()
    cached = _SEMAPHORES.get(loop)
    if cached is not None and cached[0] == MAX_CONCURRENT:
        return cached[1]
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    _SEMAPHORES[loop] = (MAX_CONCURRENT, semaphore)
    return semaphore


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


def _rechazar_si_content_length_excede(request: Request) -> None:
    """Chequeo barato de Content-Length.

    Va ANTES de adquirir el semáforo a propósito: un 413 obvio no debe gastar
    un lugar de la cola ni tiempo de CPU. El tope real se vuelve a aplicar
    leyendo el stream (body chunked sin Content-Length).
    """
    content_length = request.headers.get("content-length")
    if content_length is None:
        return
    try:
        declared = int(content_length)
    except ValueError:
        return  # header inválido: que decida el stream
    if declared > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            413, {"code": "too_large", "message": "El archivo supera el tamaño máximo."}
        )
    if declared == 0:
        raise HTTPException(400, {"code": "invalid_pdf", "message": "Archivo vacío."})


@app.post("/extract", response_model=ExtractResponse)
async def extract(request: Request):
    content_type = request.headers.get("content-type", "")
    is_multipart = content_type.lower().startswith("multipart/form-data")

    if not is_multipart:
        # Content-Length primero: es barato y no debe hacer cola.
        _rechazar_si_content_length_excede(request)

    semaphore = _get_semaphore()
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=QUEUE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        # No se lee el cuerpo: el PDF de la petición que espera no entra en memoria.
        raise HTTPException(
            503,
            {
                "code": "overloaded",
                "message": "El servicio está saturado. Reintentá en unos segundos.",
            },
            headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
        )

    try:
        if is_multipart:
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
            # (El Content-Length ya se validó arriba, antes del semáforo.)
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
            # PyMuPDF es CPU-bound
            result = await asyncio.to_thread(extract_text, data, OUTPUT_FORMAT)
        except ExtractionError as exc:
            raise HTTPException(
                _STATUS.get(type(exc), 400), {"code": exc.code, "message": str(exc)}
            )

        return ExtractResponse(content=result.content, page_count=result.page_count)
    finally:
        # Siempre se libera: error de dominio, 400/413, o cliente que se
        # desconectó mientras subía el PDF (request.stream()/form() pueden abortar).
        semaphore.release()
