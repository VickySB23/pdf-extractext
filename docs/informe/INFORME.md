# Informe Técnico: Test de Carga, Estrés y Optimización de Microservicio

**Materia:** Desarrollo de Software
**Institución:** Universidad Tecnológica Nacional – Facultad Regional San Rafael (UTN FRSR)
**Integrantes:** Julieta Valentina Bignet, Victoria Sanchez Bujaldon
**Repositorio:** https://github.com/VickySB23/pdf-extractext/tree/parte-dos
**Versión medida:** commit `b3f9540` (mediciones finales). Un refactor posterior, sin cambios de comportamiento, se describe en la sección 8.

---

## 1. Introducción y objetivo

El objetivo del trabajo es diseñar, evaluar y optimizar un microservicio de extracción de texto de archivos PDF, con salida en formato Markdown, en un entorno contenerizado y con recursos limitados. Se evalúan su resiliencia, latencia y rendimiento con dos herramientas de carga: Grafana k6 (modelo cerrado, prueba *spike*) y Vegeta (modelo abierto, tasa constante), y se comparan los resultados con los valores de referencia de la cátedra.

---

## 2. Arquitectura de la solución y decisiones de diseño

### 2.1 Topología

```
k6 / Vegeta ──► Traefik v3.6 (puerto 8080) ──► 5 réplicas de extraction-service
                (reparto round robin)           (1 CPU y 512 MiB cada una)
                                                PDF entra ► Markdown sale (JSON)
```

### 2.2 Componentes

- **Endpoint:** `POST /extract`. Acepta el PDF como *body* binario (`Content-Type: application/pdf`) o como `multipart/form-data`. Responde `200` con `{"content": "<markdown>", "page_count": N}`.
- **Stack:** Python 3.12, FastAPI y uvicorn. Extracción con PyMuPDF.
- **Contenerización y escalado:** `docker-compose.yml` con `deploy.replicas: 5` y límites `cpus: 1.0` y `memory: 512M` por réplica. Se levanta con `docker compose up --build`.
- **Reverse proxy:** Traefik v3.6 descubre las réplicas por etiquetas de Docker y reparte el tráfico en *round robin*.
- **Backpressure (control de saturación):** un semáforo por réplica (`MAX_CONCURRENT=1`). Una petición que no consigue lugar espera hasta `QUEUE_TIMEOUT_SECONDS=20` s; si se agota, recibe `503 Service Unavailable` con la cabecera `Retry-After`. El semáforo se adquiere **antes de leer el cuerpo** del request, de modo que las peticiones que esperan no retienen su PDF en memoria.
- **Candado de PyMuPDF:** PyMuPDF no admite uso concurrente desde varios hilos (lo indica su documentación). Dentro de cada proceso la extracción se serializa; el paralelismo real sale de las 5 réplicas.
- **Markdown:** conversión liviana propia (títulos según el tamaño de la fuente, viñetas y párrafos). El interruptor `OUTPUT_FORMAT=markdown|text` permite volver al texto plano.
- **Fuera del benchmark:** `document-service` y MongoDB (primera etapa del proyecto) permanecen en el repositorio; su compose es `docker-compose.full.yml`.

### 2.3 Twelve-Factor App

- **III. Configuración:** todas las opciones por variables de entorno (`MAX_CONCURRENT`, `QUEUE_TIMEOUT_SECONDS`, `RETRY_AFTER_SECONDS`, `MAX_UPLOAD_SIZE_BYTES`, `OUTPUT_FORMAT`, `PORT`), validadas al arrancar: si una es inválida, el servicio no inicia y explica por qué.
- **VI. Procesos:** el servicio no guarda estado. En el camino principal (cuerpo binario) no se escribe a disco; el modo `multipart` puede usar archivos temporales de la biblioteca web para partes grandes.
- **VII. Port binding:** el puerto se define con `PORT`.
- **XI. Logs:** salida a *stdout*.
- **Seguridad:** el proceso corre con un usuario sin privilegios dentro del contenedor.

---

## 3. Cuello de botella identificado

La extracción de texto es una tarea limitada por CPU: dentro del contenedor cuesta ~216 ms por PDF (5 repeticiones por archivo, media sobre los 4 PDFs oficiales). Como estimación, con 5 CPU y ~20,3 req/s medidos, cada petición consume unos 246 ms de CPU, de los cuales la extracción representa cerca del 88 %.

Con 5 réplicas de 1 CPU el techo teórico ronda los **23 req/s en texto plano**. Se midieron **19,60 req/s** en texto plano y **12,95 req/s** con Markdown.

---

## 4. Metodología de medición

- **Equipo:** una sola PC con 6 núcleos físicos (12 lógicos); Docker Desktop con 12 CPUs y ~9,4 GB de RAM. k6/Vegeta, Traefik y las réplicas comparten esa CPU.
- **Datos:** los 4 PDFs oficiales de `tests/stress/pdfs` (16, 42, 62 y 90 páginas; hasta 8,9 MB).
- **Pruebas:** `tests/stress/k6-spike.js` (100 usuarios, 40 s) y Vegeta a 50 req/s durante 30 s con timeout de 30 s (`run-vegeta.ps1` / `run-vegeta.sh`).
- **Procedimiento:** las réplicas se reinician y se espera a que estén sanas antes de cada corrida, para que el atraso de una prueba no contamine la siguiente.
- **Dónde se mide:** desde Windows (programas locales) y **dentro de la red de Docker** (k6 y Vegeta como contenedores). Las mediciones dentro de Docker se repitieron 3 veces; las de Windows son una sola corrida.
- **Evidencia:** todas las salidas crudas están en `docs/mediciones/`, y el registro de cada experimento en `docs/mediciones/00-registro.md`.

---

## 5. Proceso de investigación y cronología de experimentos

| # | Experimento / hipótesis | Resultado | Decisión |
|---|---|---|---|
| 1 | **Baseline:** pypdf, 1 réplica, sin control de concurrencia | k6: 1,49 req/s, 86,9 % de error. Vegeta: 0 % de éxito (1.500 timeouts) | Punto de partida |
| – | Comparación de librerías con los 4 PDFs oficiales | pypdf ~2.100–2.500 ms por PDF; PyMuPDF ~166 ms (12 a 15 veces más rápido) | Cambiar a PyMuPDF |
| 2 | PyMuPDF, 1 réplica, sin protección | k6: 4,38 req/s, 13,5 % de error. Vegeta: 4,4 %. Memoria posterior ~870 MiB (supera los 512 MiB del enunciado) | Falta controlar la saturación |
| 3 | **Backpressure:** semáforo antes del cuerpo + `503` | Misma capacidad (4,44 req/s); errores controlados, latencia máxima acotada a ~20 s; memoria pico 352–512 MiB | Se mantiene |
| 4 | `MAX_CONCURRENT=2`, 1 réplica | Sin mejora de throughput; memoria sube a 699 MiB | Descartado |
| 5 | **5 réplicas** (1 CPU / 512 MiB) | k6: 11,70 req/s, 0 % de error. Vegeta: 7,7 %. RAM pico 126–187 MiB por réplica; ninguna terminó por falta de memoria | Se mantiene |
| 6 | Diagnóstico: ¿dónde se pierde capacidad? | Extracción en contenedor ~216 ms (166 ms en el host). k6 desde la red de Docker: **20,30 req/s** contra 11,70 desde Windows | Se mide también dentro de Docker |
| 7 | Alternativas de extracción (flags de PyMuPDF, pdfium) | Diferencias de 6–12 %, dentro del ruido (la misma función midió 166 y 217 ms en dos corridas) | Descartado |
| 8 | Balanceo `p2c` vs round robin (3 corridas c/u) | 20,29 vs 20,30 req/s | Se mantiene round robin |
| 9 | Vegeta dentro de la red de Docker (texto plano, 3 corridas) | 19,5 % de éxito (18,7 / 20,5 / 19,4 %); 7,7 % desde Windows | Medición de referencia |
| 10 | `MAX_CONCURRENT=2` con 5 réplicas | k6 20,36 req/s; Vegeta 21,0 %. Dentro del ruido; sin falta de memoria | Descartado |
| 11 | **Markdown:** `pymupdf4llm` vs conversión propia | `pymupdf4llm`: 3,7 s contra 23 ms de texto plano en un PDF de 16 páginas. Conversión propia: +40 % de CPU (240 ms vs 172 ms por PDF) | Conversión propia liviana |
| 12 | **Medición final** con Markdown (5 réplicas, Traefik) | k6 dentro de Docker: 12,95 req/s. Vegeta dentro de Docker: 15,8 % | Configuración final |
| 13 | Misma configuración con `OUTPUT_FORMAT=text` | k6 dentro de Docker: 19,60 req/s | El Markdown cuesta ~34 % de throughput |
| 14 | Refactor (DRY, YAGNI, KISS) | Salidas idénticas en los 4 PDFs (SHA-256), 54 tests. Control de k6: 14,16 req/s, 0 % de error (una corrida) | Se incorpora (ver sección 8) |

**Aprendizajes:**
- El mayor salto vino del cambio de librería de extracción (12 a 15 veces por PDF), no del balanceo ni de la concurrencia.
- El backpressure no aumenta la capacidad: evita el colapso (sin él, con pypdf, Vegeta daba 0 % porque todas las peticiones competían por la CPU y vencían) y protege la memoria.
- Varias "mejoras" aparentes caían dentro de la variación entre corridas (hasta ~9 %), por eso se repitieron las mediciones.
- El entorno cuenta: el mismo código rindió 11,7 req/s medido desde Windows y 20,3 req/s dentro de la red de Docker.

---

## 6. Resultados

### 6.1 Antes vs. después (mediciones desde Windows, una corrida)

| Métrica | Antes (Exp. 1: pypdf, 1 réplica, sin control) | Después (final: PyMuPDF, 5 réplicas, backpressure, Markdown) |
|---|---|---|
| k6: throughput | 1,49 req/s | 5,88 req/s |
| k6: tasa de error | 86,9 % | 1,1 % |
| k6: latencia mediana (p50) | 50,5 s | 11,6 s |
| k6: latencia máxima | 60,0 s | 22,5 s |
| Vegeta: tasa de éxito | 0 % (1.500 timeouts) | 8,3 % (125 / 1.500) |

### 6.2 Comparación con la cátedra (mediciones dentro de la red de Docker, 3 corridas)

**Tabla A: prueba spike con k6 (100 usuarios, 40 s)**

| Métrica | Cátedra | Final (Markdown) | Final (`OUTPUT_FORMAT=text`) |
|---|---|---|---|
| Peticiones procesadas | 1.037 | 554 | 796 |
| Throughput sostenido | 25,35 req/s | 12,95 req/s | 19,60 req/s |
| Tasa de error | 0,00 % | 0,00 % | 0,00 % |
| Latencia mediana (p50) | 1,88 s | 6,76 s | 4,57 s |
| Latencia p90 | 7,83 s | 8,27 s | 5,51 s |
| Latencia p95 | 8,80 s | 8,58 s | 5,71 s |
| Latencia máxima | 13,94 s | 9,28 s | 6,37 s |

**Tabla B: carga fija con Vegeta (50 req/s, 30 s, timeout de 30 s)**

| Métrica | Cátedra | Final (Markdown) |
|---|---|---|
| Peticiones exitosas (200) | 998 / 1.500 (66,53 %) | 237 / 1.500 (15,8 %) |
| Rechazos controlados (`503`) | no informa | ~1.260 (~84 %) |
| Timeouts / error de conexión (código 0) | 501 (33,40 %) | ~4 (~0,3 %) |
| Latencia mediana (p50) | 14,89 s | 20,05 s (corrida 1; coincide con el tope de espera en cola) |

Con texto plano, la tasa de éxito de Vegeta fue de ~19,5 % (Exp. 9, medida antes de incorporar Markdown).

---

## 7. Análisis y comparación con la cátedra

No se superaron los valores de referencia de la cátedra ni en throughput ni en la tasa de éxito de Vegeta. En k6 se alcanzó el 77 % del throughput de la cátedra con texto plano (19,60 de 25,35 req/s) y el 51 % con Markdown (12,95 req/s). En compensación, se obtuvieron 0 % de error y latencias máximas menores (9,28 s contra 13,94 s).

Se identifican dos efectos distintos:

1. **Costo del Markdown.** La conversión propia reduce el throughput un ~34 % respecto del texto plano (19,60 a 12,95 req/s), coherente con el +40 % de CPU medido por PDF. Explica la diferencia entre nuestras dos configuraciones, no la que queda con la cátedra.
2. **Diferencia restante con la cátedra (texto plano, 19,60 contra 25,35 req/s).** No pudimos determinar su causa. Se desconocen el hardware y el sistema operativo de la medición de la cátedra, mientras que nosotros medimos en una sola PC con Windows y Docker Desktop, donde observamos que la capa de red costaba capacidad (11,7 contra 20,3 req/s para el mismo código). La ruta de archivos del script de la cátedra sugiere un entorno Linux, pero es una inferencia.

**Vegeta (modelo abierto).** Con una capacidad de ~13 req/s frente a 50 req/s inyectados, la mayor parte de las peticiones no puede atenderse. El servicio rechaza el exceso rápidamente con `503` (~84 %) en lugar de dejarlo vencer por timeout (~0,3 %, frente al 33,4 % de la cátedra). Aun así, Vegeta cuenta el `503` como no exitoso, de modo que el rechazo controlado no mejora la tasa de éxito. Su valor es evitar el colapso: sin backpressure se observaron picos de ~870 MiB de memoria con un límite de 512 MiB y un 0 % de éxito.

---

## 8. Calidad del código y pruebas

- **Pruebas:** 54 pruebas automáticas en `services/extraction-service` (contrato HTTP, backpressure, configuración, Markdown, extracción), con ~94 % de cobertura de líneas.
- **Refactor DRY / YAGNI / KISS:** se eliminó código repetido (construcción de errores HTTP, constantes de formato, validación duplicada de la firma `%PDF-`), código inalcanzable y reglas sin efecto medible (por ejemplo, la detección de subtítulos por nombre de fuente, que no cambiaba el resultado en los 4 PDFs oficiales). Funciones largas se dividieron en funciones pequeñas.
- **Verificación de que no cambió el comportamiento:** se compararon los hashes SHA-256 de la salida (Markdown y texto plano) de los 4 PDFs oficiales antes y después: los 8 resultaron idénticos.
- **Control de rendimiento posterior:** una corrida de k6 dentro de Docker dio 14,16 req/s, 0 % de error, p50 6,18 s y p95 7,92 s. Al ser una sola corrida, no se afirma una mejora respecto de 12,95 req/s.
- **Comentarios:** se conservaron solo los que explican decisiones no evidentes (límite de hilos de PyMuPDF, bandera de lectura de texto, orden del semáforo, etc.).

---

## 9. Limitaciones y trabajo futuro

**Limitaciones**
1. **Entorno de medición.** Las mediciones desde Windows y dentro de la red de Docker difieren mucho (11,7 contra 20,3 req/s). Atribuirlo a la red de Docker Desktop es una inferencia.
2. **Hardware compartido.** Generadores de carga, Traefik y réplicas comparten los núcleos de una misma PC.
3. **Variación entre corridas.** Una misma configuración varió hasta ~9 %. Las mediciones desde Windows son de una sola corrida.
4. **Markdown básico.** Detecta títulos por tamaño de fuente, viñetas y párrafos; no reconstruye tablas, y algunos PDFs no producen viñetas (por ejemplo, `scrum_manager_historias_usuario.pdf` dio 0). Las letras capitulares quedan como párrafos sueltos.
5. **Requisito de Markdown.** Se consultó a la cátedra sobre si el Markdown era obligatorio y no hubo respuesta por escrito; por eso `OUTPUT_FORMAT` es configurable.
6. **Licencia.** PyMuPDF se distribuye bajo AGPL-3.0 (o licencia comercial): aceptable en el ámbito académico, pero requiere evaluación para otros usos.
7. **Código heredado.** El `document-service` conserva un cliente HTTP con el contrato anterior del servicio de extracción; no forma parte del flujo medido.

**Trabajo futuro:** probar otro proxy (por ejemplo Caddy), mejorar la conversión a Markdown, repetir las mediciones en Linux nativo y reducir el costo por PDF.

---

## 10. Instrucciones de reproducción

```bash
docker compose up --build          # levanta Traefik y las 5 réplicas (puerto 8080)
k6 run tests/stress/k6-spike.js    # prueba spike
```

Prueba de carga fija con Vegeta:

```bash
./tests/stress/run-vegeta.sh mi-prueba            # Linux / macOS / Git Bash
```
```powershell
.\tests\stress\run-vegeta.ps1 -Label mi-prueba    # Windows
```

Mediciones dentro de la red de Docker (3 corridas): `.\tests\stress\run-k6-docker.ps1 -Label etiqueta -Runs 3` y `.\tests\stress\run-vegeta-docker.ps1 -Label etiqueta -Runs 3`. Para texto plano: variable de entorno `OUTPUT_FORMAT=text`.
