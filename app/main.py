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


def create_app_services() -> DocumentService:
    """Build application services and wire their infrastructure dependencies."""
    settings = get_settings()
    logger.info(f"Conectando a MongoDB en: {settings.mongo_uri} (DB: {settings.mongo_db_name})")
    client = AsyncIOMotorClient(settings.mongo_uri)
    db = client[settings.mongo_db_name]
    document_service = DocumentService(
        pdf_service=PDFService(),
        repository=MongoDocumentRepository(db),
    )
    logger.info("Servicios ensamblados e inyectados correctamente.")
    return document_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle."""
    logger.info("--- Iniciando Sistema de Gestión de Documentos PDF ---")
    app.state.document_service = create_app_services()
    get_settings().upload_dir.mkdir(parents=True, exist_ok=True)
    yield
    logger.info("--- Sistema apagado correctamente ---")


app = FastAPI(
    title="Sistema de Gestión de Documentos PDF",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(document_router)
