# PDF Extract: microservicios para extraer y gestionar texto de PDFs

Trabajo práctico universitario de Desarrollo de Software.
Universidad Tecnológica Nacional, Facultad Regional San Rafael, Ingeniería en Sistemas.
Año 2026.
Integrantes: Julieta Bignet y Victoria Sanchez Bujaldon.
Repositorio: https://github.com/VickySB23/pdf-extractext, rama `microservicios`.

Este README documenta el stack de microservicios y las pruebas de carga. El monolito de la etapa 1 está en la rama `monolito`.

## 1. Descripción

El sistema recibe un PDF, extrae su texto y lo guarda en MongoDB para consultarlo, editarlo o borrarlo.
Se compone de dos microservicios detrás de un API Gateway:

- **document-service:** API REST con el CRUD de documentos en `/api/documents`. Calcula el checksum SHA-256 del archivo, rechaza duplicados y persiste el texto en MongoDB.
- **extraction-service:** expone `POST /extract`, recibe un PDF y devuelve `{"content": "...", "page_count": N}`. Acepta el archivo como cuerpo binario o como `multipart/form-data`. No guarda estado y corre con 5 réplicas.

El texto se entrega en Markdown liviano por defecto, configurable a texto plano.

## 2. Arquitectura

```text
Cliente, k6 o Vegeta
    |
    v
Traefik :8080 <-- lee las rutas --- Consul :8500 <-- se registra cada réplica
    |
    |--- /extract ------------------> 5 réplicas de extraction-service
    |                                        ^
    | /api/documents, /health                | /extract
    v                                        |
document-service ----------------------------+
    |
    v
MongoDB
```

- Cada réplica se registra en Consul al arrancar, con ID propio, chequeo HTTP y sus rutas como tags, y se da de baja al apagarse. Traefik descubre las rutas desde Consul, sin labels en el compose ni acceso al socket de Docker.
- Traefik balancea `/extract` con estrategia `p2c`, también para las llamadas de `document-service`.
- Traefik aplica el rate limit (`429`, por defecto 20 req/s con ráfaga de 40 por cliente) y el circuit breaker. Su expresión excluye el `503`, porque es un rechazo controlado de la cola.
- `document-service` reintenta hasta 3 veces los errores de conexión, `429`, `502` y `504`. No reintenta timeouts ni un `503` de cola llena.
- El backpressure se implementa con un cupo por réplica, `503` y header `Retry-After`. El cupo se adquiere antes de leer el cuerpo para no retener PDFs en memoria.
- `document-service` envía cada PDF a `extraction-service` como cuerpo binario y guarda el Markdown devuelto.
- El PDF se procesa en memoria, sin archivos temporales. El checksum se calcula sobre el archivo y un índice único evita duplicados.
- La extracción usa PyMuPDF por su mejor rendimiento frente a `pypdf`. El Markdown es una conversión propia y liviana: títulos, viñetas y párrafos.
- Cada contenedor tiene límites de CPU y memoria; las réplicas usan 1 CPU y 512 MiB.
- Las imágenes propias están versionadas: `pdf-extraction-service:v1.0.0` y `pdf-document-service:v1.0.0`.
- La configuración entra por variables de entorno y los logs salen por stdout.

Cada servicio se organiza en capas: `core` (configuración y logs), `domain` (solo en extraction-service), `application` (casos de uso), `infrastructure` (PyMuPDF, MongoDB, Consul y clientes HTTP) y `presentation` (rutas y esquemas HTTP).

## 3. Tecnologías

| Área | Herramienta |
| --- | --- |
| Lenguaje y framework | Python 3.12, FastAPI, Uvicorn |
| Extracción | PyMuPDF |
| Persistencia | MongoDB 7, PyMongo Async |
| API Gateway | Traefik v3.6 |
| Descubrimiento de servicios | Consul 1.21 |
| Contenedores | Docker y Docker Compose |
| Dependencias | uv, con versiones fijadas en `uv.lock` |
| Pruebas | pytest, k6 y Vegeta |
| Seguridad | Trivy |

## 4. Requisitos

- Git.
- Docker Desktop en Windows o macOS, o Docker Engine con el plugin Compose v2 en Linux.
- Se recomiendan 8 GB de RAM: los límites de los contenedores suman cerca de 5 GB.
- Los puertos `8080`, `8081` y `8500` libres.
- Opcional, para correr los tests unitarios: Python 3.11 o superior y [uv](https://docs.astral.sh/uv/).
- Opcional, para las pruebas de carga desde el host: k6 y Vegeta. Los scripts `*-docker.ps1` los ejecutan como contenedores.

## 5. Instalación y ejecución

```bash
git clone https://github.com/VickySB23/pdf-extractext.git
cd pdf-extractext
docker compose up --build -d --wait
docker compose ps
```

`git clone` descarga la rama `microservicios`, que es la predeterminada.
`--wait` espera a que todos los contenedores estén sanos. La primera vez tarda unos minutos porque construye las imágenes.

Para cambiar la configuración, copiá `.env.example` como `.env` antes de levantar. Ninguna variable es obligatoria.

| URL | Qué es |
| --- | --- |
| `http://localhost:8080` | API Gateway: `/api/documents`, `/extract` y `/health` |
| `http://localhost:8081` | Dashboard de Traefik (solo en desarrollo) |
| `http://localhost:8500` | Interfaz de Consul (solo en desarrollo) |

Los dashboards los agrega `docker-compose.override.yml`, que Compose carga solo. Para levantar sin ellos: `docker compose -f docker-compose.yml up --build -d --wait`.

Para detener:

```bash
docker compose down      # conserva los documentos guardados
docker compose down -v   # borra también la base de datos
```

## 6. API

| Método | Ruta | Uso |
| --- | --- | --- |
| `GET` | `/health` | Estado de `document-service` y MongoDB. |
| `POST` | `/api/documents` | Sube un PDF, extrae el texto y lo guarda. |
| `GET` | `/api/documents` | Lista hasta 100 documentos. |
| `GET` | `/api/documents/{id}` | Consulta un documento. |
| `PUT` | `/api/documents/{id}` | Actualiza el texto; el checksum sigue identificando el archivo original. |
| `DELETE` | `/api/documents/{id}` | Elimina un documento. |
| `POST` | `/extract` | Extrae el texto sin guardarlo. |

La respuesta de `/api/documents` incluye `id`, `original_filename`, `full_text`, `checksum` y `created_at`.
El router valida la extensión `.pdf`; `extraction-service` valida el archivo vacío, el tamaño máximo de 10 MB y la firma `%PDF-`. Una subida sin `Content-Length` se rechaza con `411`.

Respuesta de ejemplo de `/extract`, abreviada:

```json
{"content": "# Ken Schwaber & Jeff Sutherland La Guía de Scrum ...\n\n# Propósito de la Guía Scrum\n\nDesarrollamos Scrum a principios de la década de 1990. ...", "page_count": 16}
```

## 7. Cómo probarlo

Con el stack levantado, desde la raíz del repositorio. En PowerShell, escribí `curl.exe` en lugar de `curl`.

```bash
curl http://localhost:8080/health
curl -X POST http://localhost:8080/api/documents \
  -F "file=@tests/stress/pdfs/Filosofia Lean.pdf;type=application/pdf"
curl http://localhost:8080/api/documents
curl -X POST http://localhost:8080/extract \
  -H "Content-Type: application/pdf" \
  --data-binary "@tests/stress/pdfs/2020-Scrum-Guide-Spanish-Latin-South-American.pdf"
```

Al repetir la subida, la API responde `400` porque el documento ya existe.

Para probar con un cliente HTTP como Postman, Bruno o Insomnia:

| Prueba | Petición | Body |
| --- | --- | --- |
| Extraer | `POST http://localhost:8080/extract` | Binario con el PDF y `Content-Type: application/pdf` |
| Subir | `POST http://localhost:8080/api/documents` | `form-data`, clave `file`, tipo archivo |
| Editar | `PUT http://localhost:8080/api/documents/{id}` | JSON: `{"new_text": "Texto nuevo"}` |
| Borrar | `DELETE http://localhost:8080/api/documents/{id}` | Sin body |

Para ver la tolerancia a fallos, apagá una réplica. Consul muestra una instancia menos y la recupera al volver a iniciarla:

```bash
docker stop pdf-extractext-extraction-service-5
docker start pdf-extractext-extraction-service-5
```

## 8. Configuración

Variables de `extraction-service`. El compose inyecta las de Consul, cola, formato y rate limit, y deja el tamaño máximo con su default.

| Variable | Default | Uso |
| --- | --- | --- |
| `MAX_UPLOAD_SIZE_BYTES` | `10485760` | Tamaño máximo aceptado para el PDF. |
| `QUEUE_TIMEOUT_SECONDS` | `20` | Tiempo máximo de espera antes de responder `503`. |
| `RETRY_AFTER_SECONDS` | `1` | Valor del header `Retry-After` ante saturación. |
| `OUTPUT_FORMAT` | `markdown` | Formato de salida: `markdown` o `text`. |
| `CONSUL_URL` | sin definir | Dirección de Consul. Sin ella el servicio no se registra. |
| `RATE_LIMIT_AVERAGE` | `20` | Peticiones por segundo admitidas por Traefik para cada cliente. |
| `RATE_LIMIT_BURST` | `40` | Ráfaga máxima admitida por Traefik. |

Variables de `document-service`. Además usa `CONSUL_URL`, `MAX_UPLOAD_SIZE_BYTES` y las dos de rate limit.

| Variable | Valor en el compose | Uso |
| --- | --- | --- |
| `MONGO_URI` | `mongodb://db:27017` | Conexión a MongoDB. |
| `MONGO_DB_NAME` | `pdf_db` | Nombre de la base. |
| `EXTRACTION_URL` | `http://traefik` | Dirección del extraction-service, a través de Traefik. |

Los puertos internos son fijos: `8000` para `document-service` y `8001` para `extraction-service`. Traefik expone el stack en `8080`.
Cada réplica atiende una extracción por vez, porque PyMuPDF no admite hilos concurrentes.

## 9. Tests unitarios

Cada servicio tiene sus tests y se prueba por separado:

```bash
cd services/document-service
uv sync
uv run pytest -q

cd ../extraction-service
uv sync
uv run pytest -q
```

No necesitan Docker ni MongoDB: usan dobles de prueba.
El workflow `.github/workflows/ci.yml` corre los tests de los dos servicios y construye las imágenes en cada push a `microservicios`, `parte-dos` o `main`, y en cada pull request.

## 10. Pruebas de carga

k6, desde la raíz del repositorio:

```bash
k6 run tests/stress/k6-spike.js
```

Vegeta en Linux, macOS o Git Bash:

```bash
./tests/stress/run-vegeta.sh mi-prueba
```

Vegeta en Windows:

```powershell
.\tests\stress\run-vegeta.ps1 -Label mi-prueba
```

Para medir desde la red de Docker, que es como se tomaron los resultados finales:

```powershell
.\tests\stress\run-k6-docker.ps1 -Label mi-prueba -Runs 3
.\tests\stress\run-vegeta-docker.ps1 -Label mi-prueba -Runs 3
```

Otros scripts de `tests/stress/`:

| Script | Uso |
| --- | --- |
| `bench_extractors.py` | Compara `pypdf` con PyMuPDF sobre los PDFs oficiales. |
| `bench_markdown.py` | Mide el costo del Markdown frente al texto plano. |
| `bench_in_container.py` | Mide la extracción dentro de un contenedor. |
| `experimentos/bench_variantes.py` | Compara variantes de extracción: flags de PyMuPDF y pdfium. |
| `run-experiment.ps1` | Corre k6 y Vegeta desde el host con estadísticas de Docker. |
| `restart-bench.ps1` | Reinicia las réplicas y espera a que estén sanas antes de medir. |

## 11. Resultados

Los valores se toman del informe técnico en `docs/informe/INFORME.md`.

| Prueba | Referencia cátedra | Resultado final |
| --- | ---: | ---: |
| k6, throughput sostenido | 25,35 req/s | 12,78 req/s con Markdown |
| k6, tasa de error | 0 % | 0 % con Markdown |
| Vegeta, tasa de éxito | 66,53 % | 27,1 % con Markdown |
| Vegeta, timeouts | 33,40 % | 1 como máximo, de 1.500 |

No se superó la referencia de la cátedra.
Son medias de 3 corridas dentro de la red de Docker. El informe explica el análisis de capacidad, las hipótesis descartadas y el impacto del Markdown y del rate limit.

## 12. Seguridad

El 9 de noviembre de 2026, `trivy fs .` no informó vulnerabilidades, secretos ni errores de configuración. `trivy image` no informó críticas en las imágenes propias ni paquetes de Python vulnerables; quedan paquetes de Debian.

Las imágenes finales no incluyen `uv` ni `pip`, y corren con un usuario sin privilegios. MongoDB solo está en la red interna `backend` y no publica puertos.

## 13. Estructura del repositorio

```text
services/
  document-service/
    app/                   Código en capas: core, application, infrastructure, presentation
    tests/                 Tests unitarios
    Dockerfile
  extraction-service/
    app/                   Código en capas: core, domain, application, infrastructure, presentation
    tests/                 Tests unitarios
    Dockerfile
tests/stress/              Scripts k6, Vegeta, benchmarks y PDFs oficiales
docs/informe/              Informe técnico final
docs/mediciones/           Registro y salidas crudas de medición
.github/workflows/ci.yml   Tests y build de imágenes
docker-compose.yml         Stack completo
docker-compose.override.yml  Paneles para desarrollo; Compose lo carga solo
.env.example               Variables disponibles
```

## 14. Ramas

| Rama | Contenido |
| --- | --- |
| `microservicios` | Versión final: microservicios, Consul, Traefik y pruebas de carga. |
| `monolito` | Monolito de la etapa 1, corregido. |
| `parte-dos` | Versión anterior, medida antes de la migración a Consul. |
| `main` | Separación inicial del monolito. |

## 15. Limitaciones

- El listado devuelve como máximo 100 documentos y no tiene paginación.
- No hay autenticación, autorización, OCR ni frontend. Los PDFs no se guardan; solo se persiste el texto extraído.
- El gateway no publica la documentación interactiva (`/docs`).
- Los PDFs generados con LaTeX sin codificación T1 pueden extraerse con acentos separados de la letra, por ejemplo `Din´amicos`. Es como el PDF guarda el texto, no un error de la extracción.

## 16. Problemas frecuentes

| Síntoma | Causa y solución |
| --- | --- |
| `404` justo después de arrancar | Traefik solo enruta los servicios que Consul marca como sanos. Esperá unos segundos, o levantá con `--wait`. |
| Error de puerto ocupado | Otro programa usa `8080`, `8081` o `8500`. Cerralo o cambiá el puerto publicado en el compose. |
| `curl` falla en PowerShell | `curl` es un alias de `Invoke-WebRequest`. Usá `curl.exe`. |
| Ctrl+C durante el arranque deja la terminal esperando | Es un comportamiento de Docker Compose: los contenedores ya están detenidos. Cerrá la terminal y corré `docker compose down`. Con `-d --wait` no ocurre. |
| `400` al subir un PDF | El documento ya existe, el archivo no es PDF o no tiene texto extraíble. El campo `detail` dice cuál. |
| Desaparecieron los documentos | Se usó `docker compose down -v`, que borra el volumen de MongoDB. |

## 17. Licencia

El proyecto está publicado bajo licencia MIT; ver `LICENSE`.
PyMuPDF se distribuye bajo AGPL-3.0 o licencia comercial, un punto a revisar fuera del contexto académico.
