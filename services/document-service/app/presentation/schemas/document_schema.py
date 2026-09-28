"""
Esquemas de validación de datos (DTOs) usando Pydantic.
Garantizan que los datos que entran y salen de la API tengan el formato correcto.
"""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

class DocumentResponse(BaseModel):
    """Esquema de salida para un documento individual (Lo que devuelve el GET y POST)."""
    id: UUID
    original_filename: str
    full_text: str
    checksum: str
    created_at: datetime

class DocumentUpdateRequest(BaseModel):
    """Esquema de entrada para actualizar el texto de un documento (Lo que pide el PUT)."""
    new_text: str