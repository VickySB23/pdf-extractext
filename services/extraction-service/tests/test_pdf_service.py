import pytest

from app.pdf_service import EncryptedPDFError, InvalidPDFError, extract_text


def test_extrae_texto_y_page_count(pdf_con_texto):
    r = extract_text(pdf_con_texto)
    assert "Hola microservicios" in r.content
    assert r.page_count == 1


def test_rechaza_contenido_que_no_es_pdf():
    with pytest.raises(InvalidPDFError):
        extract_text(b"esto no es un pdf")


def test_pdf_sin_texto_devuelve_content_vacio():
    from tests.conftest import build_pdf

    r = extract_text(build_pdf(""))
    assert r.content == ""
    assert r.page_count == 1
