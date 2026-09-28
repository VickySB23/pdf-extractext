from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "healthy"}


def test_extract_ok(pdf_con_texto):
    r = client.post("/extract", files={"file": ("a.pdf", pdf_con_texto, "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert "Hola microservicios" in body["text"]
    assert len(body["checksum"]) == 64


def test_extract_no_pdf():
    r = client.post("/extract", files={"file": ("a.pdf", b"nope", "application/pdf")})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_pdf"
