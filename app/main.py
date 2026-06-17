"""
Ensamblador principal del sistema - Versión Refactorizada Etapa 1.
Aplica principios SOLID e Inversión de Dependencias.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core import get_settings
from app.application.services.pdf_service import PDFService
from app.application.services.document_service import DocumentService 
from app.presentation.routers.document_router import router as document_router
from motor.motor_asyncio import AsyncIOMotorClient
from app.infrastructure.repositories.mongo_repository import MongoDocumentRepository
from app.core.logger import logger

_document_service: DocumentService | None = None

def get_document_service() -> DocumentService:
    """Provee la instancia del servicio a los controladores (Inyección de Dependencias)."""
    if _document_service is None:
        logger.error("Se intentó acceder al servicio de documentos antes de inicializarlo")
        raise RuntimeError("El servicio de documentos no ha sido inicializado")
    return _document_service

def create_app_services() -> DocumentService:
    """Ensambla las capas de la aplicación siguiendo la arquitectura empresarial."""
    global _document_service
    settings = get_settings()
    logger.info(f"Conectando a MongoDB en: {settings.mongo_uri} (DB: {settings.mongo_db_name})")
    client = AsyncIOMotorClient(settings.mongo_uri)
    db = client[settings.mongo_db_name]
    _document_service = DocumentService(
        pdf_service=PDFService(),
        repository=MongoDocumentRepository(db),
    )
    logger.info("Servicios ensamblados e inyectados correctamente.")
    return _document_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación."""
    logger.info("--- Iniciando Sistema de Gestión de Documentos PDF ---")
    create_app_services()
    get_settings().upload_dir.mkdir(parents=True, exist_ok=True)
    yield
    logger.info("--- Sistema apagado correctamente ---")

app = FastAPI(
    title="Sistema de Gestión de Documentos PDF",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(document_router)