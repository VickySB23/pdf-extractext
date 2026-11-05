"""Registro de la réplica en Consul: Traefik descubre las rutas desde sus tags."""
import asyncio
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

import httpx

from app.logger import logger

NOMBRE_SERVICIO = "extraction-service"
PUERTO = 8001
# El 503 queda afuera: es el rechazo controlado de la cola, no una falla del servicio.
_EXPRESION_CORTE = "NetworkErrorRatio() > 0.5 || ResponseCodeRatio(500, 503, 0, 600) > 0.25"
TAGS = [
    "traefik.enable=true",
    "traefik.http.routers.extract.rule=Path(`/extract`)",
    "traefik.http.routers.extract.entrypoints=web",
    "traefik.http.services.extract.loadbalancer.strategy=p2c",
    "traefik.http.routers.extract.middlewares=extract-limit,extract-breaker",
    "traefik.http.middlewares.extract-limit.ratelimit.average=20",
    "traefik.http.middlewares.extract-limit.ratelimit.burst=40",
    f"traefik.http.middlewares.extract-breaker.circuitbreaker.expression={_EXPRESION_CORTE}",
]

_INTENTOS = 10
_ESPERA_SEGUNDOS = 1.0


def ip_propia(consul_url: str) -> str:
    """Devuelve la IP con la que esta réplica llega a Consul."""
    destino = urlsplit(consul_url)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((destino.hostname, destino.port or 80))
        return sock.getsockname()[0]


class RegistroConsul:
    def __init__(
        self,
        cliente: httpx.AsyncClient,
        ip: str,
        id_instancia: str | None = None,
        esperar: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._cliente = cliente
        self._ip = ip
        self._id = id_instancia or f"{NOMBRE_SERVICIO}-{socket.gethostname()}"
        self._esperar = esperar

    def _definicion(self) -> dict:
        return {
            "ID": self._id,
            "Name": NOMBRE_SERVICIO,
            "Address": self._ip,
            "Port": PUERTO,
            "Tags": TAGS,
            "Check": {
                "HTTP": f"http://{self._ip}:{PUERTO}/health",
                "Interval": "5s",
                "Timeout": "3s",
                "DeregisterCriticalServiceAfter": "1m",
            },
        }

    async def registrar(self) -> None:
        for intento in range(1, _INTENTOS + 1):
            try:
                respuesta = await self._cliente.put(
                    "/v1/agent/service/register", json=self._definicion()
                )
                respuesta.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("Consul no disponible (intento %s): %s", intento, exc)
                await self._esperar(_ESPERA_SEGUNDOS)
                continue
            logger.info("Réplica registrada en Consul: %s", self._id)
            return
        raise RuntimeError(f"No se pudo registrar {self._id} en Consul.")

    async def desregistrar(self) -> None:
        try:
            respuesta = await self._cliente.put(f"/v1/agent/service/deregister/{self._id}")
            respuesta.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("No se pudo dar de baja %s en Consul: %s", self._id, exc)


def crear_registro(cliente: httpx.AsyncClient, consul_url: str) -> RegistroConsul:
    return RegistroConsul(cliente, ip_propia(consul_url))
