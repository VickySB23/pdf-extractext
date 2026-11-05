"""Application assembly."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from app.application.services.document_service import DocumentService
from app.application.services.pdf_service import PDFService
from app.core import get_settings
from app.core.logger import logger
from app.infrastructure.repositories.mongo_repository import MongoDocumentRepository
from app.presentation.routers.document_router import router as document_router
from app.presentation.routers.health_router import router as health_router
from app.presentation.upload_limits import keep_multipart_in_memory, reject_unbounded_uploads


def create_app_services() -> tuple[DocumentService, AsyncIOMotorClient, MongoDocumentRepository]:
    """Build application services and wire their infrastructure dependencies."""
    settings = get_settings()
    logger.info(f"Conectando a MongoDB en: {settings.mongo_uri} (DB: {settings.mongo_db_name})")
    client = AsyncIOMotorClient(settings.mongo_uri)
    db = client[settings.mongo_db_name]
    repository = MongoDocumentRepository(db)
    document_service = DocumentService(pdf_service=PDFService(), repository=repository)
    logger.info("Servicios ensamblados e inyectados correctamente.")
    return document_service, client, repository


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle."""
    logger.info("--- Iniciando Sistema de Gestión de Documentos PDF ---")
    document_service, mongo_client, repository = create_app_services()
    await repository.ensure_indexes()
    app.state.document_service = document_service
    app.state.mongo_client = mongo_client
    try:
        yield
    finally:
        app.state.mongo_client.close()
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
