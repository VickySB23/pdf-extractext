# Diagnostico de repositorio - PDF ExtractText

Fecha: 2026-10-04  
Alcance: diagnostico de solo lectura. No se modificaron archivos de codigo. Se creo unicamente este informe en `docs/diagnostico/`.

## Resumen ejecutivo

El repositorio no cumple el contrato principal del TP tal como fue descripto. Existe un `POST /extract`, pero pertenece al `extraction-service`, solo acepta `multipart/form-data`, responde `{text, checksum, pages}` y no esta expuesto publicamente por Traefik. La API publica real es `POST /api/documents`, tambien multipart, persiste en MongoDB y responde un documento CRUD con `{id, original_filename, full_text, checksum, created_at}`.

Docker Compose define Traefik, document-service, extraction-service y MongoDB, pero esta orientado a desarrollo (`--reload`, bind mounts, dashboard inseguro) y no define replicas ni limites de CPU/RAM. Tampoco pude ejecutar baseline real porque Docker Desktop no estaba levantado y faltan los PDFs oficiales/scripts de `tests/stress/pdfs`; `k6` y `vegeta` tampoco estan instalados localmente.

## Verificado vs supuesto

Verificado:
- Estructura del repo, codigo fuente, tests, Dockerfiles y `docker-compose.yml`.
- `docker compose config` renderiza una configuracion valida.
- `docker compose up --build -d` falla en este entorno porque no hay daemon Docker accesible.
- No existen archivos versionados de stress, k6, Vegeta ni PDFs oficiales.
- `k6` y `vegeta` no estan disponibles como comandos locales.

Supuesto / inferido:
- Un request `application/pdf` con body binario directo fallaria contra los endpoints actuales porque ambos usan `UploadFile = File(...)`, lo que en FastAPI requiere multipart/form-data.
- Bajo 50 req/s sostenidos, la cola efectiva quedaria en el event loop/threadpool/proceso ASGI y en MongoDB, porque no hay limite explicito de concurrencia, cola controlada ni timeout end-to-end propio.

## Hallazgos por severidad

### Critico - `POST /extract` no esta expuesto publicamente

Evidencia:
- `docker-compose.yml:41` enruta Traefik solo a `PathPrefix(/api/documents) || Path(/health)`.
- `docker-compose.yml:57-58` conecta `extraction-service` solo a `backend`, con comentario de que los clientes no llegan directo.
- `docker-compose.yml:59-66` deja comentada la configuracion opcional para exponer extraction-service.
- `services/extraction-service/app/main.py:40-41` define `@app.post("/extract")`, pero ese servicio no esta publicado por puerto ni Traefik.

Impacto:
- El evaluador que ataque `POST /extract` desde fuera del compose no llega al endpoint requerido.
- La API publica disponible es `POST /api/documents`, no el contrato del TP.

### Critico - Contrato de request/response incompatible

Evidencia:
- `services/extraction-service/app/main.py:20-23` define `ExtractResponse` con `text`, `checksum`, `pages`.
- `services/extraction-service/app/main.py:40-41` recibe `file: UploadFile = File(...)`.
- `services/document-service/app/presentation/routers/document_router.py:18-20` expone `POST /api/documents` con `file: UploadFile = File(...)`.
- `services/document-service/app/presentation/schemas/document_schema.py:9-15` responde `id`, `original_filename`, `full_text`, `checksum`, `created_at`.

Impacto:
- El contrato pedido es `200 {"content": "<markdown>", "page_count": N}`.
- La implementacion actual no devuelve `content`, no devuelve `page_count`, no convierte a Markdown y no acepta body binario directo.

### Alto - PDFs sin texto no tienen semantica consistente con el contrato

Evidencia:
- `services/extraction-service/app/pdf_service.py:50-51` lanza `NoTextError` cuando no hay texto nativo.
- `services/extraction-service/app/main.py:28-32` mapea `NoTextError` a HTTP 422.
- `services/document-service/app/application/services/pdf_service.py:35-41` lanza `ValueError` si no hay texto.
- `services/document-service/app/presentation/routers/document_router.py:46-49` transforma cualquier `ValueError` en HTTP 400.
- `services/document-service/tests/test_api.py:92-104` espera 400 para PDF sin texto en la API publica.

Impacto:
- Si el evaluador espera 200 con `content: ""` o un comportamiento uniforme para PDFs escaneados, hoy falla.
- Ademas, el comportamiento difiere entre el servicio interno (`422`) y el publico (`400`).

### Alto - El flujo publico no usa el microservicio de extraccion

Evidencia:
- `services/document-service/app/main.py:23-25` ensambla `DocumentService(pdf_service=PDFService(), repository=MongoDocumentRepository(db))`.
- `services/document-service/app/application/services/document_service.py:19` ejecuta `self._pdf_service.extract_text` localmente con `asyncio.to_thread`.
- `services/document-service/app/infrastructure/clients/http_text_extractor.py:23-61` implementa un cliente HTTP a `/extract`, pero no esta inyectado en `main.py`.
- `docker-compose.yml:26` define `EXTRACTION_URL`, pero `services/document-service/app/core/config.py:9-15` no declara esa variable y `main.py` no la usa.

Impacto:
- Hay un salto de arquitectura incompleto: el compose levanta extraction-service, pero el request publico procesa el PDF dentro de document-service.
- MongoDB queda en el camino del endpoint publico, aunque el TP pide un microservicio stateless de extraccion.

### Alto - Compose no define replicas ni limites de recursos

Evidencia:
- Comando: `rg -n "deploy|replicas|resources|cpus|mem_limit|memswap_limit|scale" docker-compose.yml`
- Salida: `NO_MATCHES`
- `docker-compose.yml:22`, `docker-compose.yml:48` y `docker-compose.yml:71` usan `container_name`, lo que dificulta escalar servicios con multiples replicas del mismo servicio.
- `services/document-service/Dockerfile:21` tiene `--workers 4`, pero `docker-compose.yml:34` lo pisa con `--reload`.
- `services/extraction-service/Dockerfile:14` no define workers y `docker-compose.yml:51` tambien usa `--reload`.

Impacto:
- No cumple el requisito de hasta 5 replicas con limites por replica, por ejemplo 1 CPU y 512 MB.
- En compose actual no hay control de CPU/RAM por contenedor.

### Alto - Compose esta en modo desarrollo, no produccion

Evidencia:
- `docker-compose.yml:7` habilita `--api.insecure=true` en Traefik.
- `docker-compose.yml:13` publica el dashboard `8080:8080`.
- `docker-compose.yml:32-34` bind mount de app y `uvicorn --reload` en document-service.
- `docker-compose.yml:49-51` bind mount de app y `uvicorn --reload` en extraction-service.

Impacto:
- `--reload` agrega watcher, reinicios y overhead, y no es adecuado para benchmark.
- El dashboard inseguro expuesto es aceptable en dev, pero no en produccion.

### Medio - Cuellos de botella de CPU/memoria por extraccion con pypdf

Evidencia:
- `services/extraction-service/pyproject.toml:7-10` depende de FastAPI, Uvicorn, pypdf y python-multipart.
- `services/extraction-service/app/pdf_service.py:38` crea `PdfReader(io.BytesIO(data))`.
- `services/extraction-service/app/pdf_service.py:46` recorre paginas y llama `page.extract_text()`.
- `services/extraction-service/app/main.py:42` lee el archivo completo en memoria.
- `services/extraction-service/app/main.py:51` manda la extraccion a `asyncio.to_thread`.
- `services/document-service/app/presentation/routers/document_router.py:31` tambien lee el archivo completo en memoria.
- `services/document-service/app/application/services/document_service.py:19` tambien usa `asyncio.to_thread`.

Impacto:
- Cada request carga el PDF completo en memoria y luego crea un `BytesIO`; bajo concurrencia, RAM escala con cantidad de requests simultaneos y tamano de PDF.
- `pypdf` es trabajo CPU-bound en Python. `to_thread` evita bloquear el event loop, pero no garantiza paralelismo CPU real si el trabajo queda limitado por el GIL.

### Medio - No hay backpressure explicita

Evidencia:
- No se encontro middleware, semaforo, cola o limitador de concurrencia en los servicios.
- `services/extraction-service/app/main.py:15` solo limita tamano maximo del upload.
- `services/document-service/app/core/config.py:13` solo limita tamano maximo.
- `services/document-service/app/infrastructure/clients/circuit_breaker.py:10-43` existe, pero aplica solo al cliente HTTP no inyectado en el flujo real.

Impacto:
- Con 50 req/s sostenidos, el sistema aceptaria requests hasta saturar workers/threadpool/Mongo/CPU.
- El resultado esperable bajo saturacion es aumento fuerte de latencia, timeouts aguas arriba o errores 5xx/connection reset, pero no una degradacion controlada con 429/503.

### Medio - MongoDB esta en el camino del endpoint publico

Evidencia:
- `services/document-service/app/application/services/document_service.py:21` consulta duplicados por checksum.
- `services/document-service/app/application/services/document_service.py:33` guarda el documento.
- `services/document-service/app/infrastructure/repositories/mongo_repository.py:42-44` usa `count_documents`.
- `services/document-service/app/infrastructure/repositories/mongo_repository.py:10-18` hace `insert_one`.

Impacto:
- La latencia y disponibilidad del endpoint publico dependen de MongoDB.
- Esto no coincide con un microservicio de extraccion stateless que solo devuelve contenido y cantidad de paginas.

### Bajo - Twelve-Factor parcialmente cumplido

Evidencia positiva:
- Config por entorno: `services/document-service/app/core/config.py:9-15`, `docker-compose.yml:23-26`.
- Logs a stdout: `services/document-service/app/core/logger.py:11`.
- Servicio de extraccion stateless en codigo: `services/extraction-service/app/main.py` no persiste datos.

Evidencia negativa:
- `services/document-service/app/main.py:38` crea `upload_dir` local aunque no guarde PDFs.
- `docker-compose.yml:32-34` y `49-51` montan codigo fuente y usan reload.
- `document-service` es stateful por dependencia directa de MongoDB en el request publico.

Impacto:
- La base Twelve-Factor esta, pero el compose actual mezcla dev/prod y el endpoint publico no es stateless.

## Docker / Compose

Verificado:
- `docker compose config` renderizo correctamente servicios `traefik`, `document-service`, `extraction-service`, `db`, redes `backend`, `traefik-net` y volumen `mongo_data`.
- Puertos publicados: `80:80` y `8080:8080` en Traefik (`docker-compose.yml:11-13`).
- MongoDB no publica puerto externo (`docker-compose.yml:69-77`).
- `extraction-service` no publica puerto externo ni esta en `traefik-net` (`docker-compose.yml:46-58`).

Fallo de arranque real:

```text
Comando: docker compose up --build -d
Salida:
unable to get image 'mongo:7.0': error during connect: Get "http://%2F%2F.%2Fpipe%2FdockerDesktopLinuxEngine/v1.51/images/mongo:7.0/json": open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
```

Interpretacion: Docker CLI y Compose estan instalados, pero Docker Desktop/daemon Linux no estaba disponible en este entorno, por lo que no pude verificar build completo desde cero.

Versiones disponibles:

```text
docker --version
Docker version 28.3.2, build 578ccf6

docker compose version
Docker Compose version v2.39.1-desktop.1
```

## Baseline k6 / Vegeta

No ejecutado por bloqueos verificables del entorno y del repo:

```text
Comando: Test-Path tests/stress/pdfs
Salida:
False
MISSING tests/stress/pdfs
```

```text
Comando: rg --files ... | rg "(stress|k6|vegeta|pdfs|\\.pdf$|\\.js$|\\.hcl$)"
Salida:
docs\architecture\diagrams\07-flujo-pdfservice.puml
```

```text
Comando: k6 version
Salida:
k6 : El termino 'k6' no se reconoce como nombre de un cmdlet...

Comando: vegeta -version
Salida:
vegeta : El termino 'vegeta' no se reconoce como nombre de un cmdlet...
```

Tambien fallo `docker compose ps` por daemon no disponible:

```text
error during connect: Get "http://%2F%2F.%2Fpipe%2FdockerDesktopLinuxEngine/v1.51/containers/json?...": open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
```

Metricas solicitadas no disponibles:
- Throughput k6: no medido.
- Tasa de exito/error k6: no medido.
- Throughput Vegeta: no medido.
- p50/p90/p95/max: no medido.
- CPU/memoria por contenedor (`docker stats`): no medido.

## Lista priorizada de cambios sugeridos

1. Exponer publicamente `POST /extract` por Traefik y/o hacer que document-service sirva exactamente ese endpoint.
2. Cambiar el contrato a `application/pdf` binario y `multipart/form-data`, si ambos son requeridos, detectando `Content-Type` y parseando ambos caminos.
3. Responder exactamente `{"content": "<markdown>", "page_count": N}`; en extraction-service ya existe `pages`, pero hay que renombrar y retirar `checksum` del contrato publico.
4. Definir la semantica de PDFs sin texto segun la catedra: si deben ser error, documentarla y unificar status/detail; si deben ser 200 vacio, cambiar validacion.
5. Quitar MongoDB del camino de `/extract`; dejar persistencia CRUD separada de la extraccion evaluada.
6. Usar el `extraction-service` real desde el flujo publico o eliminar el servicio duplicado; hoy hay dos extractores divergentes.
7. Crear un compose de produccion o perfiles `dev/prod`: sin `--reload`, sin bind mounts de codigo, sin dashboard insecure expuesto.
8. Agregar replicas y limites: por ejemplo `deploy.replicas`, `deploy.resources.limits.cpus`, `memory`, y evitar `container_name` para poder escalar.
9. Definir workers por servicio de forma consistente: varios procesos para CPU-bound o replicas horizontales; no depender solo de `asyncio.to_thread`.
10. Agregar backpressure explicita: semaforo por proceso, timeout de request, limite de body a nivel proxy/app y respuesta 429/503 cuando se satura.
11. Agregar scripts versionados de k6 y Vegeta y commitear los 4 PDFs oficiales en `tests/stress/pdfs` o documentar como obtenerlos.
12. Medir de nuevo con Docker activo: `docker compose up --build`, smoke test a `/extract`, k6 spike 100 VUs 40s, Vegeta 50 req/s 30s timeout 30s, y `docker stats` durante ambas corridas.

