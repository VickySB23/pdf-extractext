import pytest
import uuid
from datetime import datetime, timezone
from tinydb import TinyDB
from tinydb.storages import MemoryStorage
from app.infrastructure.repositories.nosql_repository import TinyDBSummaryRepository
from app.application.interfaces.summary_repository import Summary

@pytest.fixture
def memory_db():
    # Usamos MemoryStorage para que la base de datos se borre al terminar el test
    db = TinyDB(storage=MemoryStorage)
    yield db
    db.close()

@pytest.mark.asyncio
async def test_save_and_check_duplicate(memory_db):
    # 1. Preparamos el repositorio
    repo = TinyDBSummaryRepository(memory_db)
    
    # 2. Creamos un documento de prueba (con ID y fecha en None para que el repo los genere)
    fake_summary = Summary(
        id=None, 
        original_filename="test.pdf",
        summary_text="Resumen IA",
        full_text="Texto extraído completo del PDF",
        checksum="abcd1234huelladigital",
        created_at=None
    )
    
    # 3. Probamos guardar usando await
    await repo.save(fake_summary)
    
    # 4. Verificamos que se haya guardado y tenga la huella digital correcta
    results = await repo.get_all()
    assert len(results) == 1
    assert results[0].checksum == "abcd1234huelladigital"
    
    # 5. Probamos la regla anti-duplicados del profe
    assert await repo.exists_by_checksum("abcd1234huelladigital") == True
    assert await repo.exists_by_checksum("otrahuella") == False