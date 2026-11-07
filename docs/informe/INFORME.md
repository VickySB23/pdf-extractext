# Informe Técnico: Test de Carga, Estrés y Optimización de Microservicio

**Materia:** Desarrollo de Software
**Institución:** Universidad Tecnológica Nacional – Facultad Regional San Rafael (UTN FRSR)
**Integrantes:** Julieta Valentina Bignet, Victoria Sanchez Bujaldon
**Repositorio:** https://github.com/VickySB23/pdf-extractext/tree/microservicios (el monolito de la etapa 1 está en la rama `monolito`)
**Versión medida:** commit `ee50612` (corridas 40 a 43 de `docs/mediciones/`).

---

## 1. Introducción y objetivo

El objetivo del trabajo es diseñar, evaluar y optimizar un microservicio de extracción de texto de archivos PDF, con salida en formato Markdown, en un entorno contenerizado y con recursos limitados. Se evalúan su resiliencia, latencia y rendimiento con dos herramientas de carga: Grafana k6 (modelo cerrado, prueba *spike*) y Vegeta (modelo abierto, tasa constante), y se comparan los resultados con los valores de referencia de la cátedra.

---

## 2. Arquitectura de la solución y decisiones de diseño

### 2.1 Topología

```
Cliente, k6 o Vegeta ──► Traefik v3.6 (puerto 8080) ◄── rutas ── Consul ◄── registro de cada réplica
                           │  rate limit y circuit breaker
                           ├─ /extract ──────► 5 réplicas de extraction-service
                           │                   (1 CPU y 512 MiB cada una)
                           │                   PDF entra ► Markdown sale (JSON)
                           └─ /api/documents ► document-service ──► MongoDB
```

### 2.2 Componentes

- **Endpoint:** `POST /extract`. Acepta el PDF como *body* binario (`Content-Type: application/pdf`) o como `multipart/form-data`. Responde `200` con `{"content": "<markdown>", "page_count": N}`.
- **Stack:** Python 3.12, FastAPI y uvicorn. Extracción con PyMuPDF. `extraction-service` se organiza en capas `core`, `domain`, `application`, `infrastructure` y `presentation`.
- **Contenerización y escalado:** un único `docker-compose.yml` con `deploy.replicas: 5`, límites `cpus: 1.0` y `memory: 512M` por réplica, límites en los demás contenedores e imágenes versionadas. Se levanta con `docker compose up --build`.
- **Reverse proxy y descubrimiento:** cada réplica se registra en Consul con ID propio, chequeo HTTP y sus rutas como tags. Traefik v3.6 descubre las réplicas sanas desde Consul y reparte el tráfico con la estrategia `p2c`.
- **Backpressure (control de saturación):** un cupo de una extracción por réplica. Una petición que no consigue lugar espera hasta `QUEUE_TIMEOUT_SECONDS=20` s; si se agota, recibe `503 Service Unavailable` con la cabecera `Retry-After`. El cupo se adquiere **antes de leer el cuerpo** del request, de modo que las peticiones que esperan no retienen su PDF en memoria.
- **Resiliencia:** Traefik aplica rate limit y circuit breaker, declarados como tags en Consul. El circuit breaker usa `NetworkErrorRatio() > 0.5 || ResponseCodeRatio(500, 503, 0, 600) > 0.25`: excluye el `503` porque es el rechazo controlado de la cola, y con Vegeta abriría el circuito sin que el servicio esté fallando. `document-service` reintenta con espera creciente solo los fallos rápidos (conexión, `429`, `502`, `504`).
- **Una extracción por réplica:** PyMuPDF no admite uso concurrente desde varios hilos (lo indica su documentación), por lo que el cupo es fijo y el paralelismo real sale de las 5 réplicas. Hasta el refactor final existían además un candado y la variable `MAX_CONCURRENT`; el candado impedía que un valor mayor a 1 paralelizara la extracción.
- **Markdown:** conversión liviana propia (títulos según el tamaño de la fuente, viñetas y párrafos). El interruptor `OUTPUT_FORMAT=markdown|text` permite volver al texto plano.
- **Resto del stack:** `document-service` y MongoDB forman parte del mismo compose, pero no intervienen en el camino medido de `POST /extract`.

### 2.3 Twelve-Factor App

- **III. Configuración:** todas las opciones por variables de entorno (`QUEUE_TIMEOUT_SECONDS`, `RETRY_AFTER_SECONDS`, `MAX_UPLOAD_SIZE_BYTES`, `OUTPUT_FORMAT`, `RATE_LIMIT_AVERAGE`, `RATE_LIMIT_BURST`), validadas al arrancar: si una es inválida, el servicio no inicia y explica por qué.
- **VI. Procesos:** el servicio no guarda estado. El PDF se procesa en memoria, sin escribirlo a disco, tanto por cuerpo binario como por `multipart`.
- **VII. Port binding:** el servicio expone HTTP en el puerto fijo `8001` del contenedor; cada réplica es una red propia y Traefik publica el acceso.
- **XI. Logs:** salida a *stdout*.
- **Seguridad:** el proceso corre con un usuario sin privilegios dentro del contenedor. Las imágenes se construyen en dos etapas, sin `uv` ni `pip` en la imagen final. `trivy fs` no informa vulnerabilidades, secretos ni errores de configuración. `trivy image` no informa críticas ni paquetes de Python vulnerables; quedan paquetes de Debian, en su mayoría sin corrección publicada.

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
| 4 | `MAX_CONCURRENT=2`, 1 réplica | Sin mejora de throughput; memoria sube a 699 MiB. El candado de PyMuPDF serializaba la extracción, así que no podía mejorar | Descartado |
| 5 | **5 réplicas** (1 CPU / 512 MiB) | k6: 11,70 req/s, 0 % de error. Vegeta: 7,7 %. RAM pico 126–187 MiB por réplica; ninguna terminó por falta de memoria | Se mantiene |
| 6 | Diagnóstico: ¿dónde se pierde capacidad? | Extracción en contenedor ~216 ms (166 ms en el host). k6 desde la red de Docker: **20,30 req/s** contra 11,70 desde Windows | Se mide también dentro de Docker |
| 7 | Alternativas de extracción (flags de PyMuPDF, pdfium) | Diferencias de 6–12 %, dentro del ruido (la misma función midió 166 y 217 ms en dos corridas) | Descartado |
| 8 | Balanceo `p2c` vs round robin (3 corridas c/u) | 20,29 vs 20,30 req/s | Sin diferencia; el compose queda con `p2c` |
| 9 | Vegeta dentro de la red de Docker (texto plano, 3 corridas) | 19,5 % de éxito (18,7 / 20,5 / 19,4 %); 7,7 % desde Windows | Medición de referencia |
| 10 | `MAX_CONCURRENT=2` con 5 réplicas | k6 20,36 req/s; Vegeta 21,0 %. Dentro del ruido, por el mismo candado del Exp. 4; sin falta de memoria | Descartado |
| 11 | **Markdown:** `pymupdf4llm` vs conversión propia | `pymupdf4llm`: 3,7 s contra 23 ms de texto plano en un PDF de 16 páginas. Conversión propia: +40 % de CPU (240 ms vs 172 ms por PDF) | Conversión propia liviana |
| 12 | Medición con Markdown (5 réplicas, Traefik) | k6 dentro de Docker: 12,95 req/s. Vegeta dentro de Docker: 15,8 % | Configuración final |
| 13 | Misma configuración con `OUTPUT_FORMAT=text` | k6 dentro de Docker: 19,60 req/s | El Markdown cuesta ~34 % de throughput |
| 14 | Refactor (DRY, YAGNI, KISS) | Salidas idénticas en los 4 PDFs (SHA-256), 54 tests. Control de k6: 14,16 req/s, 0 % de error (una corrida) | Se incorpora (ver sección 8) |
| 15 | Un cupo fijo por réplica | Se elimina `MAX_CONCURRENT` y el candado, que impedían paralelizar con cualquier valor | Se incorpora |
| 16 | Consul para el descubrimiento | Con Vegeta, las 5 réplicas siguieron sanas en las 14 muestras; una réplica caída sale en menos de 12 s y vuelve sola | Se incorpora |
| 17 | Circuit breaker en Traefik, excluyendo el `503` | Con un servicio de prueba, 60 respuestas `503` no abrieron el circuito; con `500` se abrió tras 11 | Se incorpora |
| 18 | Rate limit de 20 req/s y ráfaga de 40 | Vegeta con Markdown pasa de ~15 % a 27,1 % de éxito; k6 con Markdown sigue con 0 % de error | Se incorpora |
| 19 | **Medición final** (3 corridas por prueba) | k6 con Markdown: 12,78 req/s. Vegeta con Markdown: 27,1 % | Configuración final |

**Aprendizajes:**
- El mayor salto vino del cambio de librería de extracción (12 a 15 veces por PDF), no del balanceo ni de la concurrencia.
- El backpressure no aumenta la capacidad: evita el colapso (sin él, con pypdf, Vegeta daba 0 % porque todas las peticiones competían por la CPU y vencían) y protege la memoria.
- Varias "mejoras" aparentes caían dentro de la variación entre corridas (hasta ~9 %), por eso se repitieron las mediciones.
- El entorno cuenta: el mismo código rindió 11,7 req/s medido desde Windows y 20,3 req/s dentro de la red de Docker.

---

## 6. Resultados

### 6.1 Antes vs. después de la primera optimización (desde Windows, una corrida, commit `b3f9540`)

| Métrica | Antes (Exp. 1: pypdf, 1 réplica, sin control) | Después (PyMuPDF, 5 réplicas, backpressure, Markdown) |
|---|---|---|
| k6: throughput | 1,49 req/s | 5,88 req/s |
| k6: tasa de error | 86,9 % | 1,1 % |
| k6: latencia mediana (p50) | 50,5 s | 11,6 s |
| k6: latencia máxima | 60,0 s | 22,5 s |
| Vegeta: tasa de éxito | 0 % (1.500 timeouts) | 8,3 % (125 / 1.500) |

### 6.2 Comparación con la cátedra (mediciones dentro de la red de Docker, 3 corridas)

**Tabla A: prueba spike con k6 (100 usuarios, 40 s), con Markdown**

| Métrica | Cátedra | Final (media de 3 corridas) |
|---|---|---|
| Peticiones procesadas | 1.037 | 544 |
| Throughput sostenido | 25,35 req/s | 12,78 req/s (12,38 a 13,38) |
| Tasa de error | 0,00 % | 0,00 % |
| Latencia mediana (p50) | 1,88 s | 6,72 s |
| Latencia p90 | 7,83 s | 8,53 s |
| Latencia p95 | 8,80 s | 8,98 s |
| Latencia máxima | 13,94 s | 9,83 s |

**Tabla B: carga fija con Vegeta (50 req/s, 30 s, timeout de 30 s)**

| Métrica | Cátedra | Final con Markdown | Final con `OUTPUT_FORMAT=text` |
|---|---|---|---|
| Peticiones exitosas (200) | 998 / 1.500 (66,53 %) | 407 / 1.500 (27,1 %; corridas: 20,6 / 29,3 / 31,5 %) | 640 / 1.500 (42,67 % en las 3 corridas) |
| Throughput efectivo | 16,65 req/s | 7,73 req/s | 15,37 req/s |
| Rechazos del rate limit (`429`) | no informa | 860 (57,3 %) | 860 (57,3 %) |
| Rechazos de la cola (`503`) | no informa | 232 (15,5 %) | 0 |
| Timeouts (código 0) | 501 (33,40 %) | 1 como máximo | 0 |
| Latencia mediana (p50) | 14,89 s | ~11 ms | ~10 ms |

El p50 final está dominado por los `429` instantáneos, así que no mide cuánto tarda una respuesta exitosa.

---

## 7. Análisis y comparación con la cátedra

No se superaron los valores de referencia de la cátedra en throughput ni en tasa de éxito. Con Markdown se alcanzó el 50 % del throughput de k6 (12,78 de 25,35 req/s), con 0 % de error y una latencia máxima menor (9,83 s contra 13,94 s). En Vegeta se obtuvo un 27,1 % de éxito contra 66,53 %, pero casi sin timeouts (como máximo 1 contra 501).

**Costo del Markdown.** La conversión propia cuesta más CPU que el texto plano (+40 % por PDF). En Vegeta, el texto plano llega a 15,37 req/s contra 7,73 req/s con Markdown, y atiende todo lo que admite el rate limit.

**Rate limit.** Traefik rechaza al instante lo que supera 20 req/s (`429`) y deja libre la CPU. El límite admite 640 de 1.500 peticiones (20 req/s durante 30 s, más la ráfaga de 40); por eso los `429` son siempre 860. Con Markdown se atienden 407 de esas 640, cerca de las ~390 que permite una capacidad de 13 req/s durante 30 s. Antes del rate limit se lograban ~237: la diferencia sugiere que el tráfico en exceso consumía capacidad, aunque no se midió por separado.

**Variación.** Vegeta con Markdown varió entre 20,6 % y 31,5 %. No se determinó la causa, por lo que el promedio debe leerse con cautela.

**Texto plano con k6.** El límite de 20 req/s está ajustado a la configuración por defecto (Markdown). En texto plano la capacidad se acerca a ese límite y k6, que reintenta de inmediato al recibir `429`, dispara muchas peticiones rechazadas: 54 % a 83 % de error, con ~17,6 respuestas exitosas por segundo. Antes del rate limit, esa configuración dio 19,60 req/s con 0 % de error. Si se usara texto plano, habría que subir el límite con `RATE_LIMIT_AVERAGE`.

**Diferencia restante con la cátedra.** No pudimos determinar su causa. Se desconocen el hardware y el sistema operativo de la medición de la cátedra, mientras que nosotros medimos en una sola PC con Windows y Docker Desktop, donde la capa de red costaba capacidad (11,7 contra 20,3 req/s para el mismo código). La ruta de archivos del script de la cátedra sugiere un entorno Linux, pero es una inferencia.

---

## 8. Calidad del código y pruebas

- **Pruebas:** 66 pruebas automáticas en `services/extraction-service` (contrato HTTP, backpressure, configuración, Markdown, extracción), con ~94 % de cobertura de líneas.
- **Refactor DRY / YAGNI / KISS:** se eliminó código repetido (construcción de errores HTTP, constantes de formato, validación duplicada de la firma `%PDF-`), código inalcanzable y reglas sin efecto medible (por ejemplo, la detección de subtítulos por nombre de fuente, que no cambiaba el resultado en los 4 PDFs oficiales). Funciones largas se dividieron en funciones pequeñas.
- **Verificación de que no cambió el comportamiento:** se compararon los hashes SHA-256 de la salida (Markdown y texto plano) de los 4 PDFs oficiales antes y después: los 8 resultaron idénticos.
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
7. **Rate limit por cliente.** El límite se calcula por dirección IP y todas las peticiones de las pruebas salen de un mismo origen. Con varios clientes reales, el reparto sería distinto.

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
