"""
Contratos de persistencia y entidad de dominio.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

@dataclass
class DocumentRecord:
    """Entidad principal: texto extraído del PDF y checksum del archivo."""
    id: UUID
    original_filename: str
    full_text: str
    checksum: str
    created_at: datetime

class DuplicateDocumentError(Exception):
    """El archivo ya fue guardado."""

    def __init__(self):
        super().__init__("Un documento con este mismo contenido ya existe en la base de datos.")

class DocumentRepository(Protocol):
    """Contrato CRUD completo (Create, Read, Update, Delete) para la base de datos."""
    async def ensure_indexes(self) -> None: ...
    async def save(self, document: DocumentRecord) -> DocumentRecord: ...
    async def get_by_id(self, doc_id: UUID) -> DocumentRecord | None: ...
    async def get_all(self) -> list[DocumentRecord]: ...
    async def update(self, doc_id: UUID, new_text: str) -> DocumentRecord | None: ...
    async def delete(self, doc_id: UUID) -> bool: ...
    async def exists_by_checksum(self, checksum: str) -> bool: ...
