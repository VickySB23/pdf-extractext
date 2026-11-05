"""Mantiene las subidas en memoria: el PDF no puede persistirse, ni temporalmente."""
from starlette.formparsers import MultiPartParser
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core import get_settings

# Margen para los límites y encabezados del multipart. El tamaño exacto del
# archivo lo valida el router, ya con el contenido en memoria.
MULTIPART_OVERHEAD_BYTES = 1024 * 1024


def _max_body_bytes() -> int:
    return get_settings().max_upload_size_bytes + MULTIPART_OVERHEAD_BYTES


def keep_multipart_in_memory() -> None:
    """Starlette pasa a disco las partes de más de 1 MB; acá subimos ese umbral."""
    MultiPartParser.spool_max_size = _max_body_bytes()


async def reject_unbounded_uploads(request: Request, call_next) -> Response:
    """Sin un tamaño declarado no se puede garantizar que el cuerpo entre en memoria."""
    if request.method != "POST" or request.url.path != "/api/documents":
        return await call_next(request)

    declared = request.headers.get("content-length", "")
    if not declared.isascii() or not declared.isdigit():
        return JSONResponse({"detail": "Falta el header Content-Length."}, status_code=411)
    if int(declared) > _max_body_bytes():
        return JSONResponse(
            {"detail": "El archivo excede el tamaño máximo permitido."}, status_code=413
        )
    return await call_next(request)
