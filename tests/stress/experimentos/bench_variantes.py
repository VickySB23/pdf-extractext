import glob
import os
import statistics
import time

import pymupdf
import pypdfium2 as pdfium

# Uso: uv run --no-project --with pymupdf --with pypdfium2 python tests/stress/experimentos/bench_variantes.py
REPETICIONES = 5


def mupdf_actual(data):
    doc = pymupdf.open(stream=data, filetype="pdf")
    texto = "\n".join(p.get_text() for p in doc)
    doc.close()
    return texto


def mupdf_sin_flags(data):
    doc = pymupdf.open(stream=data, filetype="pdf")
    texto = "\n".join(p.get_text("text", flags=0) for p in doc)
    doc.close()
    return texto


def pdfium_texto(data):
    pdf = pdfium.PdfDocument(data)
    partes = []
    for page in pdf:
        tp = page.get_textpage()
        partes.append(tp.get_text_range())
        tp.close()
        page.close()
    pdf.close()
    return "\n".join(partes)


VARIANTES = [
    ("pymupdf actual", mupdf_actual),
    ("pymupdf flags=0", mupdf_sin_flags),
    ("pdfium", pdfium_texto),
]

archivos = sorted(glob.glob(os.path.join("tests", "stress", "pdfs", "*.pdf")))
if not archivos:
    raise SystemExit("No encontré PDFs. Ejecutá desde la raíz del proyecto.")

for nombre, funcion in VARIANTES:
    medias, caracteres = [], []
    for ruta in archivos:
        with open(ruta, "rb") as f:
            datos = f.read()
        funcion(datos)
        tiempos = []
        for _ in range(REPETICIONES):
            t0 = time.perf_counter()
            texto = funcion(datos)
            tiempos.append(time.perf_counter() - t0)
        medias.append(statistics.mean(tiempos))
        caracteres.append(len(texto))
    print(f"{nombre:18} media {statistics.mean(medias) * 1000:6.0f} ms | "
          f"por PDF {[round(m * 1000) for m in medias]} | caracteres {caracteres}")
