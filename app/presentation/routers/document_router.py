"""
Controlador REST para la gestión de resúmenes.
Pertenece a la capa de Presentación: Recibe peticiones HTTP, 
valida formatos y delega el trabajo pesado a la capa de Aplicación.
"""

from uuid import UUID
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from app.application.services.summary_service import SummaryService
from app.presentation.schemas.pdf_summary import (
    SummaryResponse,
    SummaryListResponse,
    HealthResponse,
)

# El prefix "/api" se aplica automáticamente a todas las rutas de este archivo
router = APIRouter(prefix="/api", tags=["summaries"])


def get_summary_service() -> SummaryService:
    """Inyecta el servicio de aplicación en los endpoints."""
    from app.main import get_summary_service as _get_service
    return _get_service()


@router.post("/summarize", response_model=SummaryResponse)
async def summarize_pdf(
    file: UploadFile = File(...),
    service: SummaryService = Depends(get_summary_service),
):
    """
    Recibe un documento físico (PDF), solicita su análisis y retorna el resumen estructurado.
    Aplica validaciones de formato y contenido antes de delegar el proceso.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    try:
        summary = await service.create_summary(content, file.filename)
        return SummaryResponse(
            id=summary.id,
            original_filename=summary.original_filename,
            summary_text=summary.summary_text,
            created_at=summary.created_at,
        )
    except ValueError as e:
        # Captura excepciones de negocio (como el error de duplicados) y las traduce a un error HTTP 400
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/summaries", response_model=SummaryListResponse)
async def list_summaries(
    limit: int = 100,
    service: SummaryService = Depends(get_summary_service),
):
    """Devuelve una lista de todos los resúmenes almacenados en la base de datos."""
    summaries = await service.list_summaries(limit)
    return SummaryListResponse(
        summaries=[
            SummaryResponse(
                id=s.id,
                original_filename=s.original_filename,
                summary_text=s.summary_text,
                created_at=s.created_at,
            )
            for s in summaries
        ],
        total=len(summaries),
    )


@router.get("/summaries/{summary_id}", response_model=SummaryResponse)
async def get_summary(
    summary_id: UUID,
    service: SummaryService = Depends(get_summary_service),
):
    """Obtiene el detalle de un resumen específico mediante su identificador único (UUID)."""
    summary = await service.get_summary(summary_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    
    return SummaryResponse(
        id=summary.id,
        original_filename=summary.original_filename,
        summary_text=summary.summary_text,
        created_at=summary.created_at,
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(service: SummaryService = Depends(get_summary_service)):
    """Verifica el estado del sistema y la disponibilidad de la API de IA."""
    ai_available = await service._ai_provider.health_check()
    return HealthResponse(
        status="healthy" if ai_available else "degraded",
        ai_provider_available=ai_available,
    )

# Bug arreglado: Se quitó el "/api" redundante para que no quede "/api/api/summaries..."
@router.delete("/summaries/{summary_id}")
async def delete_summary(
    summary_id: UUID,
    service: SummaryService = Depends(get_summary_service)
):
    """
    Elimina de forma permanente un resumen de la base de datos.
    """
    fue_borrado = await service.delete_summary(summary_id)
    
    if not fue_borrado:
        # Estándar REST: Retornar 404 cuando se intenta operar sobre un recurso inexistente
        raise HTTPException(status_code=404, detail="Resumen no encontrado en la base de datos")
    
    return {"message": "¡Resumen eliminado exitosamente!"}