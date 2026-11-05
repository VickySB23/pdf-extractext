"""La consigna prohíbe persistir el PDF, aunque sea temporalmente, mientras se procesa."""
from tempfile import SpooledTemporaryFile
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.application.interfaces.text_extractor import InvalidPDFError
from app.core import get_settings
from app.main import app
from app.presentation.routers.document_router import get_document_service
from app.presentation.upload_limits import MULTIPART_OVERHEAD_BYTES


@pytest.fixture
def client():
    service = AsyncMock()
    service.create_document.side_effect = InvalidPDFError("rechazado después de recibirlo")
    app.dependency_overrides[get_document_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.pop(get_document_service, None)


def test_large_upload_never_rolls_over_to_disk(client, monkeypatch):
    rollovers = []
    original = SpooledTemporaryFile.rollover

    def spy(self):
        rollovers.append(self)
        original(self)

    monkeypatch.setattr(SpooledTemporaryFile, "rollover", spy)
    content = b"%PDF-" + b"x" * (9 * 1024 * 1024)

    response = client.post(
        "/api/documents", files={"file": ("grande.pdf", content, "application/pdf")}
    )

    assert response.status_code == 400
    assert rollovers == []


def test_rejects_declared_oversized_body_before_reading_it(client):
    limit = get_settings().max_upload_size_bytes + MULTIPART_OVERHEAD_BYTES

    response = client.post(
        "/api/documents",
        content=b"x",
        headers={"Content-Type": "multipart/form-data; boundary=x", "Content-Length": str(limit + 1)},
    )

    assert response.status_code == 413


def test_rejects_upload_without_declared_length(client):
    def chunks():
        yield b"--x--"

    response = client.post(
        "/api/documents",
        content=chunks(),
        headers={"Content-Type": "multipart/form-data; boundary=x"},
    )

    assert response.status_code == 411
