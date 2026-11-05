"""Implementación HTTP de TextExtractor: delega en el extraction-service a través de Traefik."""
import asyncio
from collections.abc import Awaitable, Callable

import httpx

from app.application.interfaces.text_extractor import (
    EncryptedPDFError,
    ExtractedText,
    ExtractorProtocolError,
    ExtractorUnavailableError,
    FileTooLargeError,
    InvalidPDFError,
    TextExtractionError,
)

_MSG_INVALID = "No se pudo procesar el archivo PDF. Puede estar dañado o protegido."
_MSG_ENCRYPTED = "El PDF está protegido con contraseña."
_MSG_TOO_LARGE = "El archivo excede el tamaño máximo permitido."
_MSG_UNAVAILABLE = "El servicio de extracción no está disponible. Intentá nuevamente."
_MSG_OVERLOADED = "El servicio de extracción está saturado. Reintentá en unos segundos."
_MSG_PROTOCOL = "El servicio de extracción devolvió una respuesta inválida."

# code que devuelve el extraction-service -> excepción de dominio de este servicio
_ERRORS: dict[str, tuple[type[TextExtractionError], str]] = {
    "invalid_pdf": (InvalidPDFError, _MSG_INVALID),
    "encrypted_pdf": (EncryptedPDFError, _MSG_ENCRYPTED),
}

_ATTEMPTS = 3
_BACKOFF_SECONDS = 0.5
# Solo fallos rápidos: un 503 de cola llena ya esperó y reintentarlo agrava la saturación.
_RETRYABLE_ERRORS = (httpx.ConnectError, httpx.RemoteProtocolError)
_RETRYABLE_STATUS = {429, 502, 504}


class HttpTextExtractor:
    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
        wait: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=timeout
        )
        self._wait = wait

    async def extract(self, content: bytes) -> ExtractedText:
        response = await self._post_with_retry(content)
        status = response.status_code

        if status == 200:
            return self._parse_success(response)
        if status == 413:
            raise FileTooLargeError(_MSG_TOO_LARGE)

        detail = self._detail(response)
        if status == 429 or detail.get("code") == "overloaded":
            raise ExtractorUnavailableError(
                _MSG_OVERLOADED, retry_after=response.headers.get("retry-after")
            )
        if status >= 500:
            raise ExtractorUnavailableError(_MSG_UNAVAILABLE)

        code = detail.get("code")
        error = _ERRORS.get(code) if isinstance(code, str) else None
        if error is None:
            raise ExtractorProtocolError(_MSG_PROTOCOL)
        error_type, message = error
        raise error_type(message)

    async def _post_with_retry(self, content: bytes) -> httpx.Response:
        for attempt in range(1, _ATTEMPTS + 1):
            is_last = attempt == _ATTEMPTS
            try:
                response = await self._client.post(
                    "/extract",
                    content=content,
                    headers={"Content-Type": "application/pdf"},
                )
            except _RETRYABLE_ERRORS as exc:
                if is_last:
                    raise ExtractorUnavailableError(_MSG_UNAVAILABLE) from exc
            except httpx.HTTPError as exc:
                raise ExtractorUnavailableError(_MSG_UNAVAILABLE) from exc
            else:
                if is_last or response.status_code not in _RETRYABLE_STATUS:
                    return response
            await self._wait(_BACKOFF_SECONDS * 2 ** (attempt - 1))
        raise ExtractorUnavailableError(_MSG_UNAVAILABLE)

    @staticmethod
    def _parse_success(response: httpx.Response) -> ExtractedText:
        try:
            data = response.json()
            text = data["content"]
            pages = data["page_count"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ExtractorProtocolError(_MSG_PROTOCOL) from exc

        if (
            not isinstance(text, str)
            or isinstance(pages, bool)
            or not isinstance(pages, int)
            or pages < 1
        ):
            raise ExtractorProtocolError(_MSG_PROTOCOL)

        return ExtractedText(text=text, pages=pages)

    @staticmethod
    def _detail(response: httpx.Response) -> dict:
        try:
            data = response.json()
        except (TypeError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        detail = data.get("detail")
        return detail if isinstance(detail, dict) else {}

    async def aclose(self) -> None:
        await self._client.aclose()
