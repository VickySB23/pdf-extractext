import asyncio
import json

import httpx
import pytest

from app import main
from app.core import config
from app.infrastructure import consul_client
from app.infrastructure.consul_client import RegistroConsul


def registro(handler, **kw) -> RegistroConsul:
    cliente = httpx.AsyncClient(base_url="http://consul:8500", transport=httpx.MockTransport(handler))
    return RegistroConsul(cliente, "172.20.0.5", id_instancia="extraction-service-abc", **kw)


async def sin_espera(_segundos: float) -> None:
    return None


def test_registra_la_replica_con_id_propio_y_chequeo_http():
    recibidas = []

    def handler(req):
        recibidas.append(req)
        return httpx.Response(200)

    asyncio.run(registro(handler).registrar())

    assert recibidas[0].method == "PUT"
    assert recibidas[0].url.path == "/v1/agent/service/register"
    cuerpo = json.loads(recibidas[0].content)
    assert cuerpo["ID"] == "extraction-service-abc"
    assert cuerpo["Name"] == "extraction-service"
    assert cuerpo["Address"] == "172.20.0.5"
    assert cuerpo["Port"] == 8001
    assert cuerpo["Check"]["HTTP"] == "http://172.20.0.5:8001/health"
    assert "traefik.http.routers.extract.rule=Path(`/extract`)" in cuerpo["Tags"]
    assert (
        "traefik.http.routers.extract.middlewares=extract-limit,extract-breaker" in cuerpo["Tags"]
    )


def test_el_rate_limit_sale_de_la_configuracion(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_AVERAGE", 7)
    monkeypatch.setattr(config, "RATE_LIMIT_BURST", 9)
    recibidas = []

    def handler(req):
        recibidas.append(req)
        return httpx.Response(200)

    asyncio.run(registro(handler).registrar())

    tags = json.loads(recibidas[0].content)["Tags"]
    assert "traefik.http.middlewares.extract-limit.ratelimit.average=7" in tags
    assert "traefik.http.middlewares.extract-limit.ratelimit.burst=9" in tags


def test_reintenta_hasta_que_consul_responde():
    respuestas = iter([httpx.ConnectError("caído"), httpx.Response(500), httpx.Response(200)])

    def handler(_req):
        respuesta = next(respuestas)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    asyncio.run(registro(handler, esperar=sin_espera).registrar())

    assert next(respuestas, None) is None


def test_falla_si_consul_nunca_responde():
    def handler(_req):
        return httpx.Response(500)

    with pytest.raises(RuntimeError, match="Consul"):
        asyncio.run(registro(handler, esperar=sin_espera).registrar())


def test_se_da_de_baja_con_su_id():
    recibidas = []

    def handler(req):
        recibidas.append(req)
        return httpx.Response(200)

    asyncio.run(registro(handler).desregistrar())

    assert recibidas[0].method == "PUT"
    assert recibidas[0].url.path == "/v1/agent/service/deregister/extraction-service-abc"


def test_la_baja_no_rompe_el_apagado_si_consul_no_esta():
    def handler(_req):
        raise httpx.ConnectError("caído")

    asyncio.run(registro(handler).desregistrar())


def test_sin_consul_url_no_se_registra(monkeypatch):
    monkeypatch.setattr(config, "CONSUL_URL", None)
    monkeypatch.setattr(consul_client, "ip_propia", lambda _url: pytest.fail("no debe resolver"))

    async def scenario():
        async with main.ciclo_de_vida(main.app):
            pass

    asyncio.run(scenario())


def test_el_ciclo_de_vida_registra_y_da_de_baja(monkeypatch):
    llamadas = []

    class Falso:
        async def registrar(self):
            llamadas.append("alta")

        async def desregistrar(self):
            llamadas.append("baja")

    monkeypatch.setattr(config, "CONSUL_URL", "http://consul:8500")
    monkeypatch.setattr(main, "crear_registro", lambda _cliente, _url: Falso())

    async def scenario():
        async with main.ciclo_de_vida(main.app):
            llamadas.append("sirviendo")

    asyncio.run(scenario())

    assert llamadas == ["alta", "sirviendo", "baja"]
