import glob
import os
import statistics
import sys
import time

sys.path.insert(0, "/app")
from app.pdf_service import extract_text

# Uso: python /work/bench_in_container.py
for ruta in sorted(glob.glob("/tmp/pdfs/*.pdf")):
    with open(ruta, "rb") as f:
        data = f.read()
    extract_text(data)
    reloj, cpu = [], []
    for _ in range(5):
        w0, c0 = time.perf_counter(), time.process_time()
        extract_text(data)
        reloj.append(time.perf_counter() - w0)
        cpu.append(time.process_time() - c0)
    nombre = os.path.basename(ruta)[:40]
    print(f"{nombre:40} reloj {statistics.mean(reloj) * 1000:6.0f} ms | cpu {statistics.mean(cpu) * 1000:6.0f} ms")
