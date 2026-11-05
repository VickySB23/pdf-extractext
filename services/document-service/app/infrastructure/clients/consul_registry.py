"""Registro del servicio en Consul: Traefik descubre las rutas desde sus tags."""
import asyncio
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

import httpx

from app.core.logger import logger

SERVICE_NAME = "document-service"
SERVICE_PORT = 8000
# El 503 queda afuera: es el rechazo controlado de la cola, no una falla del servicio.
_BREAKER_EXPRESSION = "NetworkErrorRatio() > 0.5 || ResponseCodeRatio(500, 503, 0, 600) > 0.25"
TAGS = [
    "traefik.enable=true",
    "traefik.http.routers.documents.rule=PathPrefix(`/api/documents`) || Path(`/health`)",
    "traefik.http.routers.documents.entrypoints=web",
    "traefik.http.routers.documents.middlewares=documents-limit,documents-breaker",
    "traefik.http.middlewares.documents-limit.ratelimit.average=20",
    "traefik.http.middlewares.documents-limit.ratelimit.burst=40",
    f"traefik.http.middlewares.documents-breaker.circuitbreaker.expression={_BREAKER_EXPRESSION}",
]

_ATTEMPTS = 10
_WAIT_SECONDS = 1.0


def own_ip(consul_url: str) -> str:
    """Devuelve la IP con la que este contenedor llega a Consul: está en dos redes."""
    target = urlsplit(consul_url)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((target.hostname, target.port or 80))
        return sock.getsockname()[0]


class ConsulRegistry:
    def __init__(
        self,
        consul_url: str,
        client: httpx.AsyncClient | None = None,
        ip: str | None = None,
        instance_id: str | None = None,
        wait: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._client = client or httpx.AsyncClient(base_url=consul_url, timeout=5.0)
        self._ip = ip or own_ip(consul_url)
        self._id = instance_id or f"{SERVICE_NAME}-{socket.gethostname()}"
        self._wait = wait

    def _definition(self) -> dict:
        return {
            "ID": self._id,
            "Name": SERVICE_NAME,
            "Address": self._ip,
            "Port": SERVICE_PORT,
            "Tags": TAGS,
            "Check": {
                "HTTP": f"http://{self._ip}:{SERVICE_PORT}/health",
                "Interval": "5s",
                "Timeout": "3s",
                "DeregisterCriticalServiceAfter": "1m",
            },
        }

    async def register(self) -> None:
        for attempt in range(1, _ATTEMPTS + 1):
            try:
                response = await self._client.put(
                    "/v1/agent/service/register", json=self._definition()
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning(f"Consul no disponible (intento {attempt}): {exc}")
                await self._wait(_WAIT_SECONDS)
                continue
            logger.info(f"Servicio registrado en Consul: {self._id}")
            return
        raise RuntimeError(f"No se pudo registrar {self._id} en Consul.")

    async def deregister(self) -> None:
        try:
            response = await self._client.put(f"/v1/agent/service/deregister/{self._id}")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(f"No se pudo dar de baja {self._id} en Consul: {exc}")
        finally:
            await self._client.aclose()
