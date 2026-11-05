"""Ensamblado de la aplicación."""
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from starlette.formparsers import MultiPartParser

from app.core import config
from app.infrastructure.consul_client import crear_registro
from app.presentation.extract_router import router as extract_router
from app.presentation.health_router import router as health_router

# Starlette pasa a disco las partes de más de 1 MB; el PDF debe quedar en memoria.
MultiPartParser.spool_max_size = config.MAX_UPLOAD_SIZE_BYTES + config.MULTIPART_OVERHEAD_BYTES


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    if config.CONSUL_URL is None:
        yield
        return
    async with httpx.AsyncClient(base_url=config.CONSUL_URL, timeout=5.0) as cliente:
        registro = crear_registro(cliente, config.CONSUL_URL)
        await registro.registrar()
        try:
            yield
        finally:
            await registro.desregistrar()


app = FastAPI(title="extraction-service", version="1.0.0", lifespan=ciclo_de_vida)
app.include_router(health_router)
app.include_router(extract_router)
