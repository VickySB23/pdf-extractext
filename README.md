# PDF ExtractText

API REST monolitica para cargar archivos PDF, extraer texto nativo en memoria y persistir documentos procesados en MongoDB.

**Desarrolladoras:**

- Julieta Bignet
- Sanchez B. Victoria

## Objetivo

El objetivo del proyecto es ofrecer un backend simple y mantenible para gestionar documentos PDF:

- recibir archivos PDF por HTTP;
- validar que el archivo sea un PDF procesable;
- extraer texto nativo con `pypdf`, sin OCR;
- calcular un checksum SHA-256 del texto extraido;
- evitar documentos duplicados por checksum;
- guardar, consultar, listar, actualizar y eliminar documentos en MongoDB.

## Estado actual

El backend monolitico se encuentra implementado con una arquitectura multicapa. Expone endpoints REST para documentos y un endpoint de salud. No incluye frontend, autenticacion, autorizacion, OCR ni generacion de resumenes.

La suite automatizada actual se ejecuta con `pytest` y cubre servicios, repositorio MongoDB simulado, endpoints de documentos y `GET /health`.

## Arquitectura

El proyecto usa una arquitectura multicapa con separacion entre presentacion, aplicacion e infraestructura:

- **Presentation**: define routers HTTP y esquemas Pydantic. Recibe requests, valida entradas basicas y devuelve respuestas JSON.
- **Application**: contiene la logica de negocio y los contratos. `DocumentService` coordina la extraccion, validacion de duplicados y persistencia; `PDFService` extrae texto y calcula checksums.
- **Infrastructure**: implementa persistencia en MongoDB mediante `motor`.
- **Core**: centraliza configuracion y logging.
- **Main**: ensambla la aplicacion FastAPI, crea servicios e inicializa/cierra el cliente MongoDB en el ciclo de vida de la app.

## Tecnologias utilizadas

| Area | Tecnologia |
| --- | --- |
| Lenguaje | Python `>=3.11` |
| Runtime Docker | `python:3.12-slim-bookworm` |
| Framework web | FastAPI |
| Servidor ASGI | Uvicorn |
| Validacion/configuracion | Pydantic, Pydantic Settings |
| Procesamiento PDF | pypdf |
| Base de datos | MongoDB |
| Driver MongoDB | motor |
| Gestion de dependencias | uv |
| Testing | pytest, pytest-asyncio, mongomock-motor |
| Contenedores | Docker, Docker Compose |

## Estructura del proyecto

```text
pdf-extractext/
|-- app/
|   |-- main.py
|   |-- core/
|   |   |-- config.py
|   |   `-- logger.py
|   |-- application/
|   |   |-- interfaces/
|   |   |   `-- document_repository.py
|   |   `-- services/
|   |       |-- document_service.py
|   |       `-- pdf_service.py
|   |-- infrastructure/
|   |   `-- repositories/
|   |       `-- mongo_repository.py
|   `-- presentation/
|       |-- routers/
|       |   |-- document_router.py
|       |   `-- health_router.py
|       `-- schemas/
|           `-- document_schema.py
|-- tests/
|   |-- test_api.py
|   |-- test_document_service.py
|   |-- test_health.py
|   |-- test_mongo_repository.py
|   `-- test_pdf_service.py
|-- Dockerfile
|-- docker-compose.yml
|-- pyproject.toml
|-- uv.lock
`-- README.md
```

## Funcionalidades implementadas

- Carga de PDFs mediante `multipart/form-data`.
- Extraccion de texto nativo del PDF en memoria.
- Rechazo de PDFs sin texto extraible.
- Rechazo de PDFs protegidos con contrasena o danados.
- Calculo de checksum SHA-256 sobre el texto extraido.
- Deteccion de duplicados por checksum antes de guardar.
- Persistencia asincrona de documentos en MongoDB.
- Listado de documentos guardados.
- Consulta de un documento por UUID.
- Actualizacion manual del texto extraido.
- Eliminacion de documentos.
- Health check contra MongoDB.

## Validaciones implementadas

En `POST /api/documents`:

- el nombre del archivo debe terminar en `.pdf`, sin distinguir mayusculas/minusculas;
- el archivo no puede estar vacio;
- el tamano maximo por defecto es `10 MB`;
- el contenido debe comenzar con la firma binaria `%PDF-`;
- el PDF no debe estar protegido con contrasena;
- el PDF debe tener texto nativo extraible;
- el contenido extraido no puede duplicar el checksum de un documento existente.

En rutas con `{doc_id}`, FastAPI valida que el identificador tenga formato UUID. Si el documento no existe, los endpoints correspondientes devuelven `404`.

## Endpoints disponibles

| Metodo | Endpoint | Descripcion |
| --- | --- | --- |
| `GET` | `/health` | Verifica conectividad con MongoDB. |
| `POST` | `/api/documents` | Sube un PDF, extrae texto y guarda el documento. |
| `GET` | `/api/documents` | Lista documentos guardados. |
| `GET` | `/api/documents/{doc_id}` | Obtiene un documento por UUID. |
| `PUT` | `/api/documents/{doc_id}` | Actualiza el campo `full_text` de un documento. |
| `DELETE` | `/api/documents/{doc_id}` | Elimina un documento por UUID. |

La documentacion interactiva de FastAPI esta disponible en:

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Respuestas principales

Un documento se devuelve con esta estructura:

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "original_filename": "documento.pdf",
  "full_text": "Texto completo extraido del documento...",
  "checksum": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
  "created_at": "2026-04-29T15:30:00+00:00"
}
```

`GET /health` devuelve:

```json
{
  "status": "healthy"
}
```

Si MongoDB no responde, devuelve HTTP `503`:

```json
{
  "status": "unhealthy"
}
```

## Variables de entorno

La configuracion se carga desde variables de entorno y, en desarrollo local, tambien desde `.env`.

| Variable | Requerida | Valor por defecto | Descripcion |
| --- | --- | --- | --- |
| `MONGO_URI` | No | `mongodb://localhost:27017` | URI de conexion a MongoDB. |
| `MONGO_DB_NAME` | No | `pdf-extractext` | Nombre de la base de datos. |
| `UPLOAD_DIR` | No | `uploads` | Directorio creado al iniciar la app. No se usa para almacenar PDFs procesados. |
| `MAX_UPLOAD_SIZE_BYTES` | No | `10485760` | Tamano maximo permitido para uploads. |

`SECRET_KEY` no es utilizada por el backend actual.

## Ejecucion local

Requisitos:

- Python `>=3.11`;
- uv;
- MongoDB accesible desde la aplicacion.

Instalar dependencias:

```bash
uv sync
```

Configurar `.env` si se quiere sobrescribir la configuracion por defecto:

```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=pdf-extractext
MAX_UPLOAD_SIZE_BYTES=10485760
```

Iniciar el servidor de desarrollo:

```bash
uv run uvicorn app.main:app --reload
```

La API queda disponible en `http://localhost:8000`.

## Docker y MongoDB

El proyecto incluye `Dockerfile` y `docker-compose.yml`.

Docker Compose levanta:

- `api`: backend FastAPI en el puerto `8000`;
- `db`: MongoDB `7.0` en el puerto `27017`;
- volumen persistente `mongo_data`.

Ejecutar con Docker Compose:

```bash
docker compose up --build
```

En Docker Compose, la API usa:

```env
MONGO_URI=mongodb://db:27017
MONGO_DB_NAME=pdf_db
```

## Tests

Ejecutar toda la suite:

```bash
uv run pytest
```

Tambien puede ejecutarse en modo resumido:

```bash
uv run pytest -q
```

## Ejemplos basicos de uso

Health check:

```bash
curl http://localhost:8000/health
```

Subir un PDF:

```bash
curl -X POST "http://localhost:8000/api/documents" \
  -F "file=@documento.pdf;type=application/pdf"
```

Listar documentos:

```bash
curl http://localhost:8000/api/documents
```

Obtener un documento:

```bash
curl http://localhost:8000/api/documents/123e4567-e89b-12d3-a456-426614174000
```

Actualizar texto extraido:

```bash
curl -X PUT "http://localhost:8000/api/documents/123e4567-e89b-12d3-a456-426614174000" \
  -H "Content-Type: application/json" \
  -d "{\"new_text\":\"Texto actualizado\"}"
```

Eliminar un documento:

```bash
curl -X DELETE "http://localhost:8000/api/documents/123e4567-e89b-12d3-a456-426614174000"
```

## Limitaciones actuales

- No hay OCR: los PDFs escaneados o basados solo en imagenes no son procesables.
- No hay frontend propio: la interaccion manual puede hacerse desde Swagger UI.
- No hay autenticacion ni autorizacion.
- No hay endpoints de resumenes.
- Los PDFs no se almacenan en disco; se procesa y persiste el texto extraido.
