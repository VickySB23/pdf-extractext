"""Ensamblado de la aplicación."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from pymongo import AsyncMongoClient

from app.application.services.document_service import DocumentService
from app.core import get_settings
from app.core.logger import logger
from app.infrastructure.clients.consul_registry import ConsulRegistry
from app.infrastructure.clients.http_text_extractor import HttpTextExtractor
from app.infrastructure.repositories.mongo_repository import MongoDocumentRepository
from app.presentation.routers.document_router import router as document_router
from app.presentation.routers.health_router import router as health_router
from app.presentation.upload_limits import keep_multipart_in_memory, reject_unbounded_uploads


def create_app_services() -> tuple[
    DocumentService, AsyncMongoClient, HttpTextExtractor, MongoDocumentRepository
]:
    """Crea los servicios y les inyecta sus dependencias de infraestructura."""
    settings = get_settings()
    logger.info(f"Conectando a MongoDB (DB: {settings.mongo_db_name})")
    client = AsyncMongoClient(settings.mongo_uri)
    db = client[settings.mongo_db_name]
    text_extractor = HttpTextExtractor(base_url=settings.extraction_url)
    repository = MongoDocumentRepository(db)
    document_service = DocumentService(extractor=text_extractor, repository=repository)
    logger.info("Servicios ensamblados e inyectados correctamente.")
    return document_service, client, text_extractor, repository


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Arranque y apagado: índices, registro en Consul y cierre de conexiones."""
    logger.info("--- Iniciando Sistema de Gestión de Documentos PDF ---")
    document_service, mongo_client, text_extractor, repository = create_app_services()
    await repository.ensure_indexes()
    app.state.document_service = document_service
    app.state.mongo_client = mongo_client
    app.state.text_extractor = text_extractor
    consul_url = get_settings().consul_url
    consul = ConsulRegistry(consul_url) if consul_url else None
    if consul:
        await consul.register()
    try:
        yield
    finally:
        if consul:
            await consul.deregister()
        await app.state.text_extractor.aclose()
        await app.state.mongo_client.close()
        logger.info("--- Sistema apagado correctamente ---")


app = FastAPI(
    title="Sistema de Gestión de Documentos PDF",
    version="1.0.0",
    lifespan=lifespan,
)

keep_multipart_in_memory()
app.middleware("http")(reject_unbounded_uploads)

app.include_router(document_router)
app.include_router(health_router)
