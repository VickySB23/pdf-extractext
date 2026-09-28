"""Implementación remota de TextExtractor: llama al extraction-service por HTTP."""
import httpx

from app.application.interfaces.text_extractor import (
    EncryptedPDFError,
    ExtractedText,
    ExtractorUnavailableError,
    InvalidPDFError,
    NoTextError,
    TextExtractionError,
)
from app.infrastructure.clients.circuit_breaker import CircuitBreaker, CircuitOpenError

# code que devuelve el extraction-service -> excepción de dominio de este servicio
_ERRORS = {
    "invalid_pdf": InvalidPDFError,
    "too_large": InvalidPDFError,
    "encrypted_pdf": EncryptedPDFError,
    "no_text": NoTextError,
}


class HttpTextExtractor:
    def __init__(
        self,
        base_url: str,
        timeout: float = 20.0,
        breaker: CircuitBreaker | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._breaker = breaker or CircuitBreaker()

    async def extract(self, filename: str, content: bytes) -> ExtractedText:
        try:
            self._breaker.before_call()
        except CircuitOpenError as exc:
            raise ExtractorUnavailableError(str(exc)) from exc

        try:
            resp = await self._client.post(
                "/extract", files={"file": (filename, content, "application/pdf")}
            )
        except httpx.HTTPError as exc:  # timeout, conexión rechazada, DNS...
            self._breaker.record_failure()
            raise ExtractorUnavailableError("extraction-service no disponible.") from exc

        if resp.status_code >= 500:
            self._breaker.record_failure()
            raise ExtractorUnavailableError("extraction-service devolvió un error interno.")

        # Un 4xx es un error del PDF, no del servicio: no cuenta para el circuit breaker
        self._breaker.record_success()

        if resp.status_code == 200:
            data = resp.json()
            return ExtractedText(data["text"], data["checksum"], data["pages"])

        detail = resp.json().get("detail", {})
        exc_cls = _ERRORS.get(detail.get("code"), TextExtractionError)
        raise exc_cls(detail.get("message", "Error de extracción."))

    async def aclose(self) -> None:
        await self._client.aclose()
