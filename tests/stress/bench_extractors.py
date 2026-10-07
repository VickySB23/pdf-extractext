import glob
import io
import os
import statistics
import time

import pymupdf
from pypdf import PdfReader

# Uso: uv run --no-project --with pymupdf --with pypdf python tests/stress/bench_extractors.py
REPETICIONES = 5


def con_pypdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def con_pymupdf(data: bytes) -> str:
    doc = pymupdf.open(stream=data, filetype="pdf")
    texto = "\n".join(p.get_text() for p in doc)
    doc.close()
    return texto


archivos = sorted(glob.glob(os.path.join("tests", "stress", "pdfs", "*.pdf")))
if not archivos:
    raise SystemExit("No encontré PDFs. Ejecutá desde la raíz del proyecto.")

resultados = {}
for nombre, funcion in [("pypdf", con_pypdf), ("pymupdf", con_pymupdf)]:
    medias = []
    for ruta in archivos:
        with open(ruta, "rb") as f:
            datos = f.read()
        funcion(datos)
        tiempos = []
        for _ in range(REPETICIONES):
            t0 = time.perf_counter()
            funcion(datos)
            tiempos.append(time.perf_counter() - t0)
        media = statistics.mean(tiempos)
        medias.append(media)
        print(f"{nombre:8} {os.path.basename(ruta)[:40]:40} {media * 1000:7.0f} ms")
    resultados[nombre] = statistics.mean(medias)
    print(f"{nombre:8} MEDIA: {resultados[nombre] * 1000:.0f} ms por PDF\n")

print(f"Mejora de pymupdf sobre pypdf: {resultados['pypdf'] / resultados['pymupdf']:.1f}x")
