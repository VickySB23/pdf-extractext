"""
Pruebas de integración para el repositorio NoSQL (TinyDB).
"""
import pytest
from tinydb import TinyDB
from tinydb.storages import MemoryStorage
from app.infrastructure.repositories.nosql_repository import TinyDBDocumentRepository
from app.application.interfaces.document_repository import DocumentRecord

@pytest.fixture
def memory_db():
    """Configura una base de datos temporal en RAM."""
    db = TinyDB(storage=MemoryStorage)  # type: ignore
    yield db
    db.close()

@pytest.mark.asyncio
async def test_save_and_check_duplicate(memory_db):
    """Verifica el flujo completo de guardado y la regla anti-duplicados."""
    
    # 1. ARRANGE
    repo = TinyDBDocumentRepository(memory_db)
    
    fake_doc = DocumentRecord(
        id=None, 
        original_filename="test.pdf",
        full_text="Texto extraído completo del PDF",
        checksum="abcd1234huelladigital",
        created_at=None
    )
    
    # 2. ACT
    await repo.save(fake_doc)
    results = await repo.get_all()
    
    # 3. ASSERT
    assert len(results) == 1
    assert results[0].checksum == "abcd1234huelladigital"
    
    # Validamos regla anti-duplicados
    assert await repo.exists_by_checksum("abcd1234huelladigital") is True
    assert await repo.exists_by_checksum("otrahuella") is False