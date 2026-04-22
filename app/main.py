"""
Punto de entrada principal (Entrypoint) de la API FastAPI.
Se encarga de la configuración global y el ensamblaje de la Arquitectura Limpia.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pathlib import Path
from tinydb import TinyDB

from app.core import get_settings
from app.application.services.pdf_service import PDFService
from app.application.services.summary_service import SummaryService
from app.infrastructure.external.nvidia_client import NvidiaAIProvider
from app.infrastructure.repositories.nosql_repository import TinyDBSummaryRepository
from app.presentation.routers.pdf_summary import router as pdf_router

# Variable global para mantener una única instancia del servicio (Patrón Singleton)
_summary_service: SummaryService | None = None

def get_summary_service() -> SummaryService:
    """Provee la instancia del servicio a los controladores (Inyección de Dependencias)."""
    if _summary_service is None:
        raise RuntimeError("La aplicación no ha sido inicializada")
    return _summary_service

def create_summary_service() -> SummaryService:
    """
    Ensambla las capas de la aplicación.
    Conecta la Infraestructura (Base de datos, IA) con la Aplicación (Servicios).
    """
    global _summary_service
    db = TinyDB('summaries_db.json')
    
    _summary_service = SummaryService(
        pdf_service=PDFService(),
        ai_provider=NvidiaAIProvider(),
        repository=TinyDBSummaryRepository(db),
    )
    return _summary_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Administra los eventos de arranque y apagado del servidor."""
    create_summary_service()
    get_settings().upload_dir.mkdir(parents=True, exist_ok=True)
    yield

# Configuración principal del framework web
app = FastAPI(
    title=get_settings().app_name,
    description="Plataforma de extracción y resumen de PDFs impulsada por IA",
    version="1.0.0",
    lifespan=lifespan,
)

# Conexión de las rutas (Endpoints)
app.include_router(pdf_router)

@app.get("/", response_class=HTMLResponse)
async def root():
    """Sirve la interfaz gráfica (Frontend) de la aplicación."""
    template_path = Path(__file__).parent / "presentation" / "templates" / "index.html"
    return template_path.read_text(encoding="utf-8")