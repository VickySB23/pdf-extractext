# PDF Extract — Test de carga, estrés y optimización de microservicio (Parte 2)

Trabajo práctico universitario de Desarrollo de Software.
Universidad Tecnológica Nacional, Facultad Regional San Rafael, Ingeniería en Sistemas.
Año 2026.
Integrantes: Julieta Bignet y Victoria Sanchez Bujaldon.
Repositorio: https://github.com/VickySB23/pdf-extractext, rama `parte-dos`.

Este README documenta la Parte 2 (secciones 1 a 8) y la puesta en marcha y validación de la Parte 1 (sección 9).

## 1. Descripción
El microservicio expone `POST /extract` para recibir un PDF y extraer su texto.
Acepta el archivo como cuerpo binario crudo o como `multipart/form-data`.
La respuesta exitosa es JSON con la forma `{"content": "...", "page_count": N}`.
El contenido se entrega en Markdown liviano por defecto, configurable a texto plano.

## 2. Arquitectura
```text
k6 / Vegeta
    |
    v
Traefik :8080
    |
    v
5 réplicas de extraction-service
1 CPU y 512 MiB por réplica
```

- `docker-compose.yml` publica Traefik en `8080:80` y enruta `/extract` y `/health`.
- Traefik balancea con estrategia `p2c`, según la etiqueta actual del compose.
- La extracción usa PyMuPDF por su mejor rendimiento frente a `pypdf`.
- El backpressure se implementa con un cupo por réplica, `503` y header `Retry-After`.
- El cupo se adquiere antes de leer el cuerpo para no retener PDFs en memoria.
- El Markdown es una conversión propia y liviana: títulos, viñetas y párrafos.
- La configuración entra por variables de entorno y los logs salen por stdout.
- La imagen ejecuta el servicio con un usuario sin privilegios.

## 3. Requisitos
- Docker con Docker Compose.
- k6 solo para ejecutar la prueba de carga tipo spike.
- Vegeta solo para ejecutar la prueba de carga fija a 50 req/s.
- PowerShell, Bash, Git Bash o una terminal equivalente para los scripts.

## 4. Cómo levantar
```bash
docker compose up --build
```
Ejemplo de llamada con un PDF del repositorio:
```bash
curl -X POST http://localhost:8080/extract \
  -H "Content-Type: application/pdf" \
  --data-binary "@tests/stress/pdfs/2020-Scrum-Guide-Spanish-Latin-South-American.pdf"
```
Respuesta de ejemplo:
Se muestra abreviada.
```json
{"content": "# Ken Schwaber & Jeff Sutherland La Guía de Scrum ...\n\n# Propósito de la Guía Scrum\n\nDesarrollamos Scrum a principios de la década de 1990. ...", "page_count": 16}
```

## 5. Configuración
Estas son las variables que lee `services/extraction-service/app/main.py`.
El compose inyecta las de cola y formato, y deja el tamaño máximo con su default.
| Variable | Default | Uso |
| --- | --- | --- |
| `MAX_UPLOAD_SIZE_BYTES` | `10485760` | Tamaño máximo aceptado para el PDF. |
| `QUEUE_TIMEOUT_SECONDS` | `20` | Tiempo máximo de espera antes de responder `503`. |
| `RETRY_AFTER_SECONDS` | `1` | Valor del header `Retry-After` ante saturación. |
| `OUTPUT_FORMAT` | `markdown` | Formato de salida: `markdown` o `text`. |

El puerto interno del contenedor es fijo: `8001`. Traefik lo expone hacia el host en `8080`.
Cada réplica atiende una extracción por vez, porque PyMuPDF no admite hilos concurrentes.

## 6. Pruebas de carga
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
Para medir desde la red de Docker se usan:
`.\tests\stress\run-k6-docker.ps1` y `.\tests\stress\run-vegeta-docker.ps1`.

## 7. Resultados
Los valores se toman del informe técnico en `docs/informe/INFORME.md`.
| Prueba | Referencia cátedra | Resultado final |
| --- | ---: | ---: |
| k6, throughput sostenido | 25,35 req/s | 12,95 req/s con Markdown |
| k6, texto plano | 25,35 req/s | 19,60 req/s con `OUTPUT_FORMAT=text` |
| Vegeta, tasa de éxito | 66,53 % | 15,8 % |

No se superó la referencia de la cátedra.
El informe explica el análisis de capacidad, las hipótesis descartadas y el impacto del Markdown.

## 8. Estructura del repositorio
```text
services/
  extraction-service/      Microservicio evaluado en la parte 2
  document-service/        Servicio de la primera etapa
tests/stress/              Scripts k6, Vegeta y PDFs oficiales
docs/informe/              Informe técnico final
docs/mediciones/           Registro y salidas crudas de medición
docker-compose.yml         Stack de benchmark con Traefik y 5 réplicas
docker-compose.full.yml    Stack completo de la primera etapa con MongoDB
```

## 9. Parte 1: stack completo con MongoDB

Esta sección documenta el stack de la primera etapa, conservado en `docker-compose.full.yml` y compuesto por `document-service`, `extraction-service`, MongoDB y Traefik. La Parte 2 (secciones 1 a 8) es el microservicio de extracción evaluado con carga.

### 9.1 Descripción y arquitectura

La primera etapa expone una API REST para subir PDFs, delegar la extracción en `extraction-service`, calcular un checksum SHA-256 del archivo, rechazar documentos duplicados y persistir los resultados en MongoDB. Incluye operaciones CRUD sobre documentos y un endpoint de salud. El router valida la extensión `.pdf`; `extraction-service` valida el archivo vacío, el tamaño máximo de 10 MB y la firma `%PDF-`. El PDF se procesa en memoria, sin archivos temporales.

```text
Cliente
  |  HTTP :80
  v
Traefik (traefik-net)
  |  /api/documents, /health
  v
document-service :8000 (traefik-net + backend)
  |                         \
  | MongoDB                 \ depends_on: service_healthy
  v                         v
MongoDB :27017          extraction-service :8001
(backend)                (backend)
```

- `traefik-net` es la red pública del gateway; `backend` es la red interna.
- Solo `document-service` está conectado a las dos redes.
- `extraction-service` y MongoDB no publican puertos al host.
- `document-service` espera el healthcheck de `extraction-service` antes de arrancar.
- `document-service` envía cada PDF a `extraction-service` como cuerpo binario y guarda el Markdown devuelto.

### 9.2 Servicios

| Servicio | Imagen / build | Puerto | Red | Función |
| --- | --- | --- | --- | --- |
| `traefik` | `traefik:v3.6` | `80` público; `8080` dashboard | `traefik-net` | Punto de entrada HTTP y ruteo. |
| `document-service` | `./services/document-service` | `8000` interno | `traefik-net`, `backend` | API de documentos y persistencia. |
| `extraction-service` | `./services/extraction-service` | `8001` interno | `backend` | Extrae el texto; el compose espera su healthcheck. |
| `db` | `mongo:7.0` | `27017` interno | `backend` | Persistencia en el volumen `mongo_data`. |

El dashboard de Traefik queda en `http://localhost:8080` y no es la API de documentos.

El compose usa el `CMD` de la imagen de `extraction-service`, sin montar el código ni reemplazar el comando. Traefik se conecta a `document-service` por la red `pdf-extractext_traefik-net`, indicada en la etiqueta `traefik.docker.network`.

### 9.3 Requisitos y puesta en marcha

- Docker Engine o Docker Desktop con Compose v2.
- Puertos `80` y `8080` libres en el host.
- `curl` para las comprobaciones (en Windows, `curl.exe`).
- No hace falta instalar Python ni `uv` en el host: las imágenes construyen sus dependencias.
- El stack de la Parte 2 (`docker-compose.yml`) también publica el puerto `8080`; no ejecutes ambos stacks a la vez.

Desde la raíz del repositorio:

```bash
docker compose -f docker-compose.full.yml up --build -d
```

El primer build puede tardar unos minutos.

### 9.4 Estado, logs y health

```bash
docker compose -f docker-compose.full.yml ps
docker compose -f docker-compose.full.yml logs -f document-service
docker compose -f docker-compose.full.yml logs -f extraction-service
docker compose -f docker-compose.full.yml logs -f traefik
```

El estado esperado es `extraction_service` en `healthy`; los demás servicios quedan `Up`. `document-service` no define healthcheck en el compose.

Para comprobar el endpoint público:

```bash
curl -i http://localhost/health
```

Respuesta esperada:

```text
HTTP/1.1 200 OK
...
{"status":"healthy"}
```

El endpoint se publica en el puerto `80` a través de Traefik.

### 9.5 Uso básico

Subir un PDF:

```bash
curl -X POST http://localhost/api/documents \
  -F "file=@documento.pdf;type=application/pdf"
```

Listar los documentos guardados:

```bash
curl http://localhost/api/documents
```

Las rutas `/api/documents/{id}` aceptan `GET`, `PUT` y `DELETE` para consultar, actualizar el texto o eliminar un documento. La respuesta de un documento incluye `id`, `original_filename`, `full_text`, `checksum` y `created_at`.

### 9.6 Detener sin borrar datos

```bash
docker compose -f docker-compose.full.yml down
```

Este comando detiene y elimina los contenedores y las redes del stack, pero conserva el volumen definido como `mongo_data` con los documentos persistidos. No uses `down -v` salvo que quieras borrar la base.

### 9.7 Pruebas realizadas

Validación manual ejecutada sobre este compose:

| Verificación | Comando | Resultado |
| --- | --- | --- |
| Configuración | `docker compose -f docker-compose.full.yml config` | Válida. |
| Arranque | `docker compose -f docker-compose.full.yml up --build -d` | Cuatro contenedores; `extraction_service` en `healthy`. |
| Salud pública | `curl -i http://localhost/health` | `200` con `{"status":"healthy"}`. |
| Carga nueva | `POST /api/documents` con un PDF de `tests/stress/pdfs/` | `200`; documento guardado. |
| Duplicado | Repetir la misma carga | `400`; mensaje de documento duplicado. |
| Listado | `GET /api/documents` | `200`; documentos devueltos. |
| Logs | `logs` de los servicios | Sin errores de infraestructura. |

La validación fue manual; no se ejecutó una suite automatizada específica para este stack. La primera petición inmediatamente después del arranque puede devolver `502` mientras `document-service` termina de iniciar; una vez listo, responde `200`.

### 9.8 Limitaciones y tareas pendientes

- `PUT /api/documents/{id}` actualiza `full_text`; el checksum sigue identificando el archivo original.
- El listado devuelve como máximo 100 documentos y no tiene paginación.
- No hay autenticación, autorización, OCR ni frontend. Los PDFs no se guardan; solo se persiste el texto extraído.
- El gateway solo publica `/api/documents` y `/health`; la documentación interactiva (`/docs`) no está expuesta.
- `document-service` no tiene healthcheck en el compose.
- La etiqueta `traefik.docker.network=pdf-extractext_traefik-net` usa el nombre de red que genera Compose para el proyecto `pdf-extractext`. Si el directorio o el nombre del proyecto cambian, hay que ajustar la etiqueta o definir `COMPOSE_PROJECT_NAME=pdf-extractext`.

### 9.9 Enlaces

- Informe final: [`docs/informe/INFORME.md`](docs/informe/INFORME.md).
- Mediciones crudas y registro: [`docs/mediciones/`](docs/mediciones/).
- Rama `main` de la primera etapa: [`main`](https://github.com/VickySB23/pdf-extractext/tree/main).

## 10. Licencia
El proyecto está publicado bajo licencia MIT; ver `LICENSE`.
PyMuPDF se distribuye bajo AGPL-3.0 o licencia comercial, un punto a revisar fuera del contexto académico.
