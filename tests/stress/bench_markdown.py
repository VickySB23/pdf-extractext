import glob
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join("services", "extraction-service"))

import pymupdf

from app.markdown_service import a_markdown

# Uso: uv run --no-project --with pymupdf python tests/stress/bench_markdown.py
REPETICIONES = 3


def plano(data: bytes) -> str:
    doc = pymupdf.open(stream=data, filetype="pdf")
    texto = "\n".join(pagina.get_text() for pagina in doc)
    doc.close()
    return texto


def markdown(data: bytes) -> str:
    doc = pymupdf.open(stream=data, filetype="pdf")
    texto = a_markdown(doc)
    doc.close()
    return texto


archivos = sorted(glob.glob(os.path.join("tests", "stress", "pdfs", "*.pdf")))
if not archivos:
    raise SystemExit("No encontré PDFs. Ejecutá desde la raíz del proyecto.")

print(f"{'PDF':44}{'plano':>11}{'markdown':>15}{'ratio':>8}")
totales = {"plano": [], "markdown": []}
for ruta in archivos:
    with open(ruta, "rb") as f:
        datos = f.read()
    medias = {}
    for nombre, funcion in (("plano", plano), ("markdown", markdown)):
        funcion(datos)
        tiempos = []
        for _ in range(REPETICIONES):
            t0 = time.perf_counter()
            funcion(datos)
            tiempos.append(time.perf_counter() - t0)
        medias[nombre] = statistics.mean(tiempos)
        totales[nombre].append(medias[nombre])
    ratio = medias["markdown"] / medias["plano"]
    print(
        f"{os.path.basename(ruta)[:44]:44}"
        f"{medias['plano'] * 1000:11.0f}"
        f"{medias['markdown'] * 1000:15.0f}"
        f"{ratio:8.2f}x"
    )

print(
    f"{'MEDIA':44}"
    f"{statistics.mean(totales['plano']) * 1000:11.0f}"
    f"{statistics.mean(totales['markdown']) * 1000:15.0f}"
)
