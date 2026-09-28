import pytest
import uuid
from datetime import datetime, timezone
from mongomock_motor import AsyncMongoMockClient
from app.infrastructure.repositories.mongo_repository import MongoDocumentRepository
from app.application.interfaces.document_repository import DocumentRecord

@pytest.fixture
def mock_db():
    client = AsyncMongoMockClient()
    return client.test_database

@pytest.fixture
def repository(mock_db):
    return MongoDocumentRepository(mock_db)

@pytest.mark.asyncio
async def test_save_and_retrieve_document(repository):
    # 1. Arrange
    doc_id = uuid.uuid4()
    doc = DocumentRecord(
        id=doc_id,
        original_filename="prueba.pdf",
        full_text="Texto extraído en el test",
        checksum="hash_de_prueba_123",
        created_at=datetime.now(timezone.utc)
    )
    
    # 2. Act
    saved_doc = await repository.save(doc)
    fetched_doc = await repository.get_by_id(doc_id)
    
    # 3. Assert
    assert saved_doc.original_filename == "prueba.pdf"
    assert saved_doc.checksum == "hash_de_prueba_123"
    assert fetched_doc is not None
    assert fetched_doc.full_text == "Texto extraído en el test"

@pytest.mark.asyncio
async def test_exists_by_checksum_logic(repository):
    # 1. Arrange
    doc = DocumentRecord(
        id=uuid.uuid4(),
        original_filename="duplicado.pdf",
        full_text="Contenido duplicado",
        checksum="hash_duplicado",
        created_at=datetime.now(timezone.utc)
    )
    await repository.save(doc)
    
    # 2. Act
    exists_true = await repository.exists_by_checksum("hash_duplicado")
    exists_false = await repository.exists_by_checksum("no_existe")
    
    # 3. Assert
    assert exists_true is True
    assert exists_false is False