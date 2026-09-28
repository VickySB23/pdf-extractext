import hashlib

import pytest

from app.pdf_service import InvalidPDFError, NoTextError, extract_text


def test_extrae_texto_y_checksum(pdf_con_texto):
    r = extract_text(pdf_con_texto)
    assert "Hola microservicios" in r.text
    assert r.pages == 1
    assert r.checksum == hashlib.sha256(r.text.encode()).hexdigest()


def test_rechaza_contenido_que_no_es_pdf():
    with pytest.raises(InvalidPDFError):
        extract_text(b"esto no es un pdf")


def test_rechaza_pdf_sin_texto():
    from tests.conftest import build_pdf

    with pytest.raises(NoTextError):
        extract_text(build_pdf(""))
