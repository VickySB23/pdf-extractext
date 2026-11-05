"""Implementación remota de TextExtractor: llama al extraction-service por HTTP."""
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
from app.infrastructure.clients.circuit_breaker import CircuitBreaker, CircuitOpenError

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


class HttpTextExtractor:
    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        breaker: CircuitBreaker | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=timeout
        )
        self._breaker = breaker or CircuitBreaker()

    async def extract(self, content: bytes) -> ExtractedText:
        try:
            self._breaker.before_call()
        except CircuitOpenError as exc:
            raise ExtractorUnavailableError(str(exc)) from exc

        try:
            response = await self._client.post(
                "/extract",
                content=content,
                headers={"Content-Type": "application/pdf"},
            )
        except httpx.HTTPError as exc:
            self._breaker.record_failure()
            raise ExtractorUnavailableError(_MSG_UNAVAILABLE) from exc

        if response.status_code >= 500:
            self._breaker.record_failure()
            detail = self._detail(response)
            if response.status_code == 503 and detail.get("code") == "overloaded":
                raise ExtractorUnavailableError(
                    _MSG_OVERLOADED,
                    retry_after=response.headers.get("retry-after"),
                )
            raise ExtractorUnavailableError(_MSG_UNAVAILABLE)

        if response.status_code == 413:
            self._breaker.record_success()
            raise FileTooLargeError(_MSG_TOO_LARGE)

        if response.status_code == 200:
            try:
                extracted = self._parse_success(response)
            except ExtractorProtocolError:
                self._breaker.record_failure()
                raise
            self._breaker.record_success()
            return extracted

        if 400 <= response.status_code < 500:
            # El servicio respondió: un error de entrada no indica indisponibilidad.
            self._breaker.record_success()
            detail = self._detail(response)
            code = detail.get("code")
            error = _ERRORS.get(code) if isinstance(code, str) else None
            if error is not None:
                error_type, message = error
                raise error_type(message)
            raise ExtractorProtocolError(_MSG_PROTOCOL)

        self._breaker.record_failure()
        raise ExtractorProtocolError(_MSG_PROTOCOL)

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
