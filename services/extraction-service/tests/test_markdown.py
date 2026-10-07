"""Markdown de /extract: títulos, viñetas, espacios, formato y su configuración.

Los PDFs se generan en el acto (insert_text / insert_htmlbox / bytes a mano),
sin dependencias nuevas. Los que llevan viñetas o espacios raros usan
insert_htmlbox: insert_text con helv (WinAnsi) no sobrevive esos caracteres.
"""
import pymupdf
from fastapi.testclient import TestClient

from app import main
from app.markdown_service import normalizar_espacios
from app.pdf_service import FORMATO_POR_DEFECTO, extract_text

client = TestClient(main.app)


def pdf_con(*lineas) -> bytes:
    """PDF de una página: cada línea es (tamaño, texto[, fuente]) vía insert_text."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    y = 72.0
    for item in lineas:
        tam, texto = item[0], item[1]
        fuente = item[2] if len(item) > 2 else "helv"
        page.insert_text((72, y), texto, fontsize=tam, fontname=fuente)
        y += tam + 20
    data = doc.tobytes()
    doc.close()
    return data


def pdf_html(html: str) -> bytes:
    """PDF de una página con HTML: acá sí sobreviven viñetas y espacios raros."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_htmlbox(pymupdf.Rect(50, 50, 545, 500), html)
    data = doc.tobytes()
    doc.close()
    return data


def test_titulo_grande_y_cuerpo_como_parrafo():
    pdf = pdf_con((24, "Titulo general"), (11, "cuerpo del texto con bastante contenido"))
    r = extract_text(pdf)
    assert r.page_count == 1
    assert r.content == "# Titulo general\n\ncuerpo del texto con bastante contenido"


def test_titulo_partido_en_dos_renglones_se_fusiona():
    pdf = pdf_con(
        (24, "Titulo partido"),
        (24, "en dos renglones"),
        (11, "cuerpo con texto suficiente para dominar el documento"),
    )
    r = extract_text(pdf)
    assert r.content == (
        "# Titulo partido en dos renglones\n\n"
        "cuerpo con texto suficiente para dominar el documento"
    )


def test_capitular_de_un_caracter_no_vuelve_titulo():
    """La letra capitular se degrada a párrafo: no se pierde el carácter."""
    pdf = pdf_con((24, "P"), (11, "arrafo con suficiente texto para ser el cuerpo"))
    r = extract_text(pdf)
    assert r.content == "P\n\narrafo con suficiente texto para ser el cuerpo"


def test_el_cuerpo_se_cuenta_por_tamano_redondeado():
    """11.0 y 11.4 son el mismo cuerpo: sin redondear, el título pasa a cuerpo."""
    pdf = pdf_con(
        (24.0, "Titulo del documento"),
        (11.0, "cuerpo de texto"),
        (11.4, "mas de la mitad"),
    )
    r = extract_text(pdf)
    assert r.content == "# Titulo del documento\n\ncuerpo de texto\n\nmas de la mitad"


def test_vinetas_se_convierten_en_guiones():
    pdf = pdf_html("<p>\u2022 primero</p><p>\u25e6 segundo</p>")
    r = extract_text(pdf)
    assert r.content == "- primero\n\n- segundo"


def test_vinetas_con_las_marcas_nuevas_se_convierten_en_guiones():
    """–, ●, ▪ y ‣ también son viñetas (ajuste sobre las marcas originales)."""
    pdf = pdf_html(
        "<p>\u2013 raya</p><p>\u25cf redonda</p><p>\u25aa cuadrada</p><p>\u2023 triplet</p>"
    )
    r = extract_text(pdf)
    assert r.content == "- raya\n\n- redonda\n\n- cuadrada\n\n- triplet"


def test_espacios_raros_se_normalizan():
    pdf = pdf_html("<p>hola&nbsp;&ensp;&ensp;mundo</p>")
    r = extract_text(pdf)
    assert "hola mundo" in r.content
    assert "\xa0" not in r.content
    assert "\u2002" not in r.content


def test_normalizar_espacios_colapsa_y_recorta():
    assert normalizar_espacios("a\u2003\u2003 b\xa0c  ") == "a b c"


def test_pdf_generado_sin_texto_devuelve_contenido_vacio():
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    r = extract_text(data)
    assert r.content == ""
    assert r.page_count == 1


def test_formato_text_devuelve_texto_plano():
    pdf = pdf_con((24, "Titulo general"), (11, "cuerpo del texto"))
    plano = extract_text(pdf, "text").content
    assert plano.startswith("Titulo general")
    assert "# Titulo general" not in plano


def test_subtitulo_en_negrita_se_vuelve_h4():
    pdf = pdf_con(
        (11, "Introduccion", "hebo"),
        (11, "cuerpo con texto suficiente para dominar el documento", "helv"),
    )
    r = extract_text(pdf)
    assert r.content == (
        "#### Introduccion\n\n"
        "cuerpo con texto suficiente para dominar el documento"
    )


def test_el_endpoint_usa_el_formato_configurado(monkeypatch):
    pdf = pdf_con((24, "Titulo general"), (11, "cuerpo del texto con bastante contenido"))
    headers = {"Content-Type": "application/pdf"}

    monkeypatch.setattr(main, "OUTPUT_FORMAT", FORMATO_POR_DEFECTO)
    r_md = client.post("/extract", content=pdf, headers=headers)
    assert r_md.status_code == 200
    assert r_md.json()["content"].startswith("# Titulo general")

    monkeypatch.setattr(main, "OUTPUT_FORMAT", "text")
    r_txt = client.post("/extract", content=pdf, headers=headers)
    assert r_txt.status_code == 200
    assert r_txt.json()["content"].startswith("Titulo general")