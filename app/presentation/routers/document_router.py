"""
Módulo de presentación (Controladores REST).
Expone la interfaz de programación de aplicaciones (API) para las operaciones CRUD.
Se encarga exclusivamente de recibir peticiones, validar formatos y retornar respuestas JSON.
"""
from uuid import UUID
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Request
from app.application.services.document_service import DocumentService
from app.presentation.schemas.document_schema import DocumentResponse, DocumentUpdateRequest

router = APIRouter(prefix="/api", tags=["documents"])

def get_document_service(request: Request) -> DocumentService:
    """Inyecta el servicio orquestador en los endpoints para desacoplar las capas."""
    return request.app.state.document_service

@router.post("/documents", response_model=DocumentResponse)
async def create_document_endpoint(
    file: UploadFile = File(...), 
    service: DocumentService = Depends(get_document_service)
):
    """
    Endpoint para subir un archivo PDF.
    Cumple con la restricción de validar el formato y procesar en memoria.
    """
    safe_filename = file.filename or "documento.pdf"
    if not safe_filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se admiten archivos PDF")
    
    content = await file.read()
    
    try:
        return await service.create_document(content, safe_filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents_endpoint(service: DocumentService = Depends(get_document_service)):
    """Lista todos los documentos procesados en el sistema."""
    return await service.list_documents()

@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document_endpoint(doc_id: UUID, service: DocumentService = Depends(get_document_service)):
    """Busca y retorna un documento específico por su ID."""
    doc = await service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return doc

@router.put("/documents/{doc_id}", response_model=DocumentResponse)
async def update_document_endpoint(
    doc_id: UUID, 
    req: DocumentUpdateRequest, 
    service: DocumentService = Depends(get_document_service)
):
    """Permite la modificación manual del texto extraído de un documento (Update del CRUD)."""
    doc = await service.update_document(doc_id, req.new_text)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado para actualizar")
    return doc

@router.delete("/documents/{doc_id}")
async def delete_document_endpoint(doc_id: UUID, service: DocumentService = Depends(get_document_service)):
    """Elimina un documento de la base de datos (Delete del CRUD)."""
    if not await service.delete_document(doc_id):
        raise HTTPException(status_code=404, detail="Documento no encontrado para eliminar")
    return {"message": "Documento eliminado"}
