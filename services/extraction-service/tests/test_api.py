from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from app.main import app
from tests.conftest import build_pdf

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "healthy"}


def test_extract_ok(pdf_con_texto):
    r = client.post("/extract", files={"file": ("a.pdf", pdf_con_texto, "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert "Hola microservicios" in body["content"]
    assert body["page_count"] == 1


def test_extract_no_pdf():
    r = client.post("/extract", files={"file": ("a.pdf", b"nope", "application/pdf")})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_pdf"


def test_extract_raw_binary_ok():
    pdf = build_pdf("hola raw")
    r = client.post("/extract", content=pdf, headers={"Content-Type": "application/pdf"})
    assert r.status_code == 200
    body = r.json()
    assert body["content"] == "hola raw"
    assert body["page_count"] == 1


def test_extract_raw_binary_sin_texto():
    pdf = build_pdf("")
    r = client.post("/extract", content=pdf, headers={"Content-Type": "application/pdf"})
    assert r.status_code == 200
    body = r.json()
    assert body["content"] == ""
    assert body["page_count"] == 1


def test_extract_raw_binary_vacio():
    r = client.post("/extract", content=b"", headers={"Content-Type": "application/pdf"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_pdf"


def test_extract_raw_binary_invalido():
    r = client.post("/extract", content=b"not pdf", headers={"Content-Type": "application/pdf"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_pdf"


def test_extract_raw_binary_demasiado_grande(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "MAX_UPLOAD_SIZE_BYTES", 10)
    pdf = build_pdf("hola")
    r = client.post("/extract", content=pdf, headers={"Content-Type": "application/pdf"})
    assert r.status_code == 413
    assert r.json()["detail"]["code"] == "too_large"


def test_extract_raw_binary_stream_por_chunks_supera_tope(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "MAX_UPLOAD_SIZE_BYTES", 10)
    pdf = build_pdf("hola")

    def chunks():
        for i in range(0, len(pdf), 16):
            yield pdf[i : i + 16]

    r = client.post("/extract", content=chunks(), headers={"Content-Type": "application/pdf"})
    assert "content-length" not in {k.lower() for k in r.request.headers}
    assert r.status_code == 413
    assert r.json()["detail"]["code"] == "too_large"


def test_extract_multipart_sin_campo_de_archivo():
    r = client.post("/extract", files={"campo": (None, "valor")})
    assert r.request.headers["content-type"].startswith("multipart/form-data")
    assert r.status_code == 400
    assert r.json()["detail"] == {"code": "invalid_pdf", "message": "No se recibió ningún archivo."}


def test_extract_cifrado():
    pdf = build_pdf("secreto")
    reader = PdfReader(BytesIO(pdf))
    writer = PdfWriter()
    for p in reader.pages:
        writer.add_page(p)
    writer.encrypt("pass")
    buf = BytesIO()
    writer.write(buf)
    pdf_enc = buf.getvalue()
    r = client.post("/extract", files={"file": ("a.pdf", pdf_enc, "application/pdf")})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "encrypted_pdf"


def test_extract_pdf_truncado():
    # MuPDF repara PDFs truncados en vez de fallar; sin páginas debe ser error.
    pdf = build_pdf("hola")
    truncado = pdf[: len(pdf) // 10]
    assert truncado.startswith(b"%PDF-")
    r = client.post("/extract", content=truncado, headers={"Content-Type": "application/pdf"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_pdf"


def test_extract_pdf_sin_objetos():
    pdf = b"%PDF-1.4\n1 0 obj\n<< >>\nendobj\ntrailer\n<< >>\n%%EOF\n"
    r = client.post("/extract", content=pdf, headers={"Content-Type": "application/pdf"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_pdf"
