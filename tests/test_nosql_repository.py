"""
Pruebas de integración para el repositorio NoSQL (TinyDB).
Verifica que la capa de persistencia se comunique correctamente con la base de datos física.
"""
import pytest
from tinydb import TinyDB
from tinydb.storages import MemoryStorage
from app.infrastructure.repositories.nosql_repository import TinyDBSummaryRepository
from app.application.interfaces.summary_repository import Summary

@pytest.fixture
def memory_db():
    """
    Configura una base de datos temporal en RAM.
    Garantiza que las pruebas sean aisladas y no ensucien la base de datos real del usuario.
    """
    # type: ignore se añade para calmar al linter sobre el tipado interno de TinyDB
    db = TinyDB(storage=MemoryStorage)  # type: ignore
    yield db
    db.close()

@pytest.mark.asyncio
async def test_save_and_check_duplicate(memory_db):
    """Verifica el flujo completo de guardado y la regla de negocio anti-duplicados."""
    
    # 1. ARRANGE (Preparar: Configurar el entorno y los datos de prueba)
    repo = TinyDBSummaryRepository(memory_db)
    
    fake_summary = Summary(
        id=None, 
        original_filename="test.pdf",
        summary_text="Resumen IA",
        full_text="Texto extraído completo del PDF",
        checksum="abcd1234huelladigital",
        created_at=None
    )
    
    # 2. ACT (Ejecutar: Llamar a los métodos del sistema que queremos probar)
    await repo.save(fake_summary)
    results = await repo.get_all()
    
    # 3. ASSERT (Comprobar: Validar que los resultados sean exactamente los esperados)
    assert len(results) == 1
    assert results[0].checksum == "abcd1234huelladigital"
    
    # Regla PEP8: Las comparaciones con booleanos usan 'is' en lugar de '=='
    assert await repo.exists_by_checksum("abcd1234huelladigital") is True
    assert await repo.exists_by_checksum("otrahuella") is False