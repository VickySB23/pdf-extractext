"""El PDF no puede persistirse, ni temporalmente, mientras se procesa."""
from tempfile import SpooledTemporaryFile

from fastapi.testclient import TestClient

from app import main
from app.core import config

client = TestClient(main.app)
MULTIPART = {"Content-Type": "multipart/form-data; boundary=x"}


def test_multipart_grande_nunca_pasa_a_disco(monkeypatch):
    rollovers = []
    original = SpooledTemporaryFile.rollover

    def espia(self):
        rollovers.append(self)
        original(self)

    monkeypatch.setattr(SpooledTemporaryFile, "rollover", espia)
    contenido = b"nope" + b"x" * (9 * 1024 * 1024)

    r = client.post("/extract", files={"file": ("a.pdf", contenido, "application/pdf")})

    assert r.status_code == 400
    assert rollovers == []


def test_multipart_sin_content_length_es_411():
    def chunks():
        yield b"--x--"

    r = client.post("/extract", content=chunks(), headers=MULTIPART)

    assert r.status_code == 411
    assert r.json()["detail"]["code"] == "length_required"


def test_multipart_que_declara_demasiado_es_413_sin_leerlo():
    limite = config.MAX_UPLOAD_SIZE_BYTES + config.MULTIPART_OVERHEAD_BYTES

    r = client.post(
        "/extract", content=b"x", headers={**MULTIPART, "Content-Length": str(limite + 1)}
    )

    assert r.status_code == 413
    assert r.json()["detail"]["code"] == "too_large"
