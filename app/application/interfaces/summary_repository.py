"""Summary Repository interface - abstraction for persistence."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Summary:
    id: UUID | None
    original_filename: str
    summary_text: str
    full_text: str
    checksum: str
    created_at: datetime | None


class SummaryRepository(ABC):
    @abstractmethod
    async def save(self, summary: Summary) -> Summary:
        pass

    @abstractmethod
    async def get_by_id(self, summary_id: UUID) -> Summary | None:
        pass

    @abstractmethod
    async def get_all(self, limit: int = 100) -> list[Summary]:
        pass
    
    @abstractmethod
    async def exists_by_checksum(self, checksum: str) -> bool:
        """Verifica si el ADN del archivo ya existe."""
        pass

    @abstractmethod
    async def delete(self, summary_id: UUID) -> bool:
        """Borra un resumen por ID (Parte del CRUD)."""
        pass