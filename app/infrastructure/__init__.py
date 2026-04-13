"""Infrastructure layer - external clients, repositories, file handling."""

from app.infrastructure.external.nvidia_client import NvidiaAIProvider
from app.infrastructure.repositories.in_memory_repository import (
    InMemorySummaryRepository,
)

__all__ = ["NvidiaAIProvider", "InMemorySummaryRepository"]
